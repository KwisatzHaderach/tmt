import datetime
import xml.etree.ElementTree as ET
from requests import post

import click

import tmt
from .junit import make_junit_xml


class ReportPolarion(tmt.steps.report.ReportPlugin):
    """
    Write test results into a Polarion run
    """
    _methods = [tmt.steps.Method(name='polarion', doc=__doc__, order=50)]
    _keys = ['project-id', 'testrun-title']

    @classmethod
    def options(cls, how=None):
        """ Prepare command line options """
        return [
            click.option(
                '--project-id', default='RedHatEnterpriseLinux7',
                help='Use specific Polarion project ID'),
            click.option(
                'testrun-title', help='Use specific TestRun title')
        ] + super().options(how)

    def go(self):
        """ Go through executed tests and report into Polarion """
        super().go()

        from tmt.export import get_polarion_ids, import_polarion
        import_polarion()
        from tmt.export import PolarionWorkItem

        title = self.opt(
            'testrun_title', self.step.plan.name + datetime.datetime.now())
        project_id = self.opt('project-id')

        properties = {
            'polarion-project-id': project_id,
            'polarion-user-id': PolarionWorkItem._session.user_id,
            'polarion-testrun-id': title,
            'polarion-project-span-ids': project_id
        }

        junit_suite = make_junit_xml(self, properties=properties)
        xml_tree = ET.fromstring(junit_suite.to_xml_string([junit_suite]))
        testsuite = xml_tree.find('testsuite')
        project_span_ids = testsuite.find(
            '*property[@name="polarion-project-span-ids"]').attrib['value']

        for result in self.step.plan.execute.results():
            work_item_id, test_project_id = get_polarion_ids(
                PolarionWorkItem.query(
                    result.id, fields=['work_item_id', 'project_id']))

            if test_project_id not in project_span_ids:
                project_span_ids += f',{test_project_id}'

            test_properties = {
                'polarion-testcase-id': work_item_id,
                'polarion-testcase-project-id': test_project_id
            }

            test_case = testsuite.find(f"*[@name='{result.name}']")
            properties_elem = ET.SubElement(test_case, 'properties')
            for name, value in test_properties.items():
                ET.SubElement(properties_elem, 'property', attrib={
                    'name': name, 'value': value})

        import pdb;pdb.set_trace()
        server_url = str(PolarionWorkItem._session._server.url)
        polarion_import_url = (
            f'{server_url}{"" if server_url.endswith("/") else "/"}'
            'import/xunit')
        auth = (
            PolarionWorkItem._session.user_id,
            PolarionWorkItem._session.password)

        response = post(
            polarion_import_url, auth=auth,
            files={'file': ('xunit.xml', ET.tostring(xml_tree))})
        self.info(f'Response code is {response.status_code}')
