'''
Notes:
    

'''
from fabric.contrib.files import append, exists, sed
from fabric.api import env, local, run, put
from pathlib import Path
from django.utils.crypto import get_random_string

REPO_URL = 'git@github.com:holden-nelson/retailtimecard.git'

def deploy():
    site_folder = f'/home/{env.user}/sites/{env.host}'
    source_folder = site_folder + '/source'
    env.use_ssh_config = True
    _create_directory_structure_if_necessary(site_folder)
    _get_latest_source(source_folder)
    _copy_secrets_file(source_folder)
    _update_settings(source_folder, env.host)
    _make_python_virtualenv(source_folder)
    _install_requirements(source_folder)
    _collect_static(source_folder)
    _run_migrations(source_folder)

def _create_directory_structure_if_necessary(site_folder):
    for subfolder in ('database', 'static', 'source'):
        run(f'mkdir -p {site_folder}/{subfolder}')

def _get_latest_source(source_folder):
    if exists(source_folder + '/.git'):
        run(f'cd {source_folder} && git fetch')
    else:
        run(f'git clone {REPO_URL} {source_folder}')
    current_commit = local("git log -n 1 --format=%H", capture=True)
    run(f'cd {source_folder} && git reset --hard {current_commit}')

def _copy_secrets_file(source_folder):
    secrets_file = '../timecardsite/secrets.py'
    remote_secrets_file = source_folder + '/timecardsite/secrets.py'
    put(secrets_file, remote_secrets_file)

def _update_settings(source_folder, site_name):
    settings_path = source_folder + '/timesheet/settings/base.py'
    
    sed(settings_path,
        'SECRET_KEY = .+$',
        f'SECRET_KEY = "{get_random_string(length=32)}"'
    )

    sed(settings_path, "DEBUG = True", "DEBUG = False")

    sed(settings_path,
        'ALLOWED_HOSTS = .+$',
        f'ALLOWED_HOSTS = ["{site_name}"]'
    )

    sed(settings_path,
        'EMAIL_BACKEND = .+$',
        ''
    )

def _make_python_virtualenv(source_folder):
    pyenv_root = '/home/dev/.pyenv'
    if not exists(pyenv_root + f'/versions/{env.host}'):
        python_version = run(f'cat {source_folder}/runtime.txt')
        run(f'pyenv install --skip-existing {python_version}')
        run(f'pyenv virtualenv {python_version} {env.host}')
        run(f'cd {source_folder} && pyenv local {env.host}')

def _install_requirements(source_folder):
    run(f'cd {source_folder} && pip install -r {source_folder}/requirements.txt')

def _collect_static(source_folder):
    run(f'cd {source_folder} && python manage.py collectstatic --noinput')

def _run_migrations(source_folder):
    run(f'cd {source_folder} && python manage.py migrate --noinput')

