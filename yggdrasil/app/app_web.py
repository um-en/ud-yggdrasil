from yggdrasil.app.app_generic import AppGeneric
from yggdrasil.app.utilities import run_cmds, generate_custom_batch
from yggdrasil.logger import logger
import os
from ygg_helpers.main import DistInfo
import shutil

_url_helpers = None


class AppWeb(AppGeneric):
    identifier = 'web'

    @classmethod
    def set_class_constants(cls, *args, **kwargs):
        global _url_helpers
        _url_helpers = kwargs.pop("url_helpers")

    def __init__(self,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = kwargs.pop("name")
        self.venv_name = 'venv_{0}'.format(self.name)
        self.url_project = kwargs.pop("url")
        self.version_py = kwargs.pop('py_version', None)
        self.repo_name = self.url_project.split("/")[-1].split(".")[0]

    # todo modularise
    def create(self, path_scripts: str, path_venvs: str, path_templates: str, **kwargs):
        logger.info("App creation for {0}: Starting...".format(self.name))
        force_regen = kwargs.pop('force_regen', False)
        debug = kwargs.pop('debug', False)

        if not self.is_installed or force_regen:
            path_venv = r'{0}\{1}'.format(path_venvs, self.venv_name)
            if self.is_installed and force_regen:
                self.remove(path_scripts, path_venvs)
            try:
                # Generate virtual environment
                cmds = []
                if not self.version_py:
                    cmds.append(r'py -m venv {0}'.format(path_venv))
                else:
                    cmds.append(r'py -{0} -m venv {1}'.format(self.version_py, path_venv))

                # Install base project & distribution meta extractor
                # TODO Parametrise bypassing SSL security
                ignore_ssl = "--trusted-host pypi.org --trusted-host files.pythonhosted.org"
                cmds.append(r'{0}\Scripts\activate && pip install {2} {1} && deactivate'.format(
                    path_venv,
                    self.url_project,
                    ignore_ssl
                ))
                cmds.append(r'{0}\Scripts\activate && pip install {2} {1} && deactivate'.format(
                    path_venv,
                    _url_helpers,
                    ignore_ssl
                ))
                run_cmds(cmds)

                # Extract distributions meta information
                cmds = []
                cmds.append(r"{0}\Scripts\activate && gen_dist_info {1} {0}\ygginfo-{1}.yaml && deactivate".format(path_venv, self.repo_name))
                cmds.append(r"{0}\Scripts\activate && gen_dist_info {1} {0}\ygginfo-{1}.yaml && deactivate".format(path_venv, "dist_meta"))
                run_cmds(cmds)
                # TODO will leave some trash, clean up dependencies too
                # TODO keep if debug mode, delete otherwise
                info_repo = DistInfo.from_yaml(r'{0}\ygginfo-{1}.yaml'.format(path_venv, self.repo_name))

                if not debug:
                    cmds = [r"{0}\Scripts\activate && pip uninstall -y dist_meta".format(path_venv)]
                    run_cmds(cmds)
                    if os.path.exists(r"{0}\ygginfo-{1}.yaml".format(path_venv, "dist_meta")):
                        os.remove(r"{0}\ygginfo-{1}.yaml".format(path_venv, "dist_meta"))

                # Installs requirements
                cmds = [r"{0}\Scripts\activate && pip install {2} -r {1}".format(
                    path_venv,
                    req.path,
                    ignore_ssl) for req in info_repo.requirements]
                run_cmds(cmds)

                # Generates batch launcher
                map_replac_eps = [[("#path_venv#", path_venv), ("#entry_point#", ep.path)] for ep in info_repo.entry_points]

                for k, mapping in enumerate(map_replac_eps):
                    generate_custom_batch(
                        source=r'{0}\template_launcher_web.txt'.format(path_templates),
                        destination=r'{0}\{1}.bat'.format(path_scripts, info_repo.entry_points[k].name),
                        replacements=mapping,
                    )

            except Exception as e:
                if not debug:
                    logger.error("App {0} could not be created - Rolling back".format(self.name))
                    self.remove(path_scripts, path_venvs, debug=debug)
                    return
                else:
                    raise e

        self.is_installed = True
        logger.info("App creation for {0}: Completed!".format(self.name))

    def remove(self, path_scripts:str, path_venvs: str, **kwargs):
        # todo update docstring
        """
        Deletes an application
        :param name: Name of the application
        """
        logger.info("App deletion for {0}: Starting...".format(self.name))
        path_venv = r'{0}\{1}'.format(path_venvs, self.venv_name)
        # Removes entry points
        if os.path.exists(path_venv):
            info_repo = DistInfo.from_yaml(r'{0}\ygginfo-{1}.yaml'.format(path_venv, self.repo_name))
            for ep in info_repo.entry_points:
                os.remove('{0}\{1}.bat'.format(path_scripts, ep.name))

        # Removes virtual environment
        if os.path.exists(path_venv):
            if not os.path.exists(r'{0}\pyvenv.cfg'.format(path_venv)) or not os.path.exists(r'{0}\Scripts\activate'.format(path_venv)):
                raise Exception("Error - The folder about to be deleted is not a virtual environment")
            else:
                shutil.rmtree(path_venv)
        self.is_installed = False
        logger.info("App deletion for {0}: Completed!".format(self.name))
