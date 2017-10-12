# -*- coding: utf-8 -*-
from errors import EnosFilePathError

from constants import SYMLINK_NAME
from datetime import datetime
from functools import wraps

import os
import yaml
import logging


def _make_env(resultdir):
    """Loads the env from `resultdir` if it exists or makes a new one.

    An Enos environment handles all specific variables of an
    experiment. This function either generates a new environment or
    loads a previous one. If the `resultdir` path is a directory that
    contains an Enos environment (i.e, env), then this function loads
    and returns it. If the `resultdir` path is empty, then this
    function makes a new environment and return it.

    In case of a directory path, this function also rereads the
    configuration file (e.g, the reservation.yaml) and reloads it.
    This lets the user update her configuration between each phase.

    Args:
        resultdir (str): directory path to make or load the env from.

    """
    env = {
        "config":      {},          # The config
        "resultdir":   "",          # Path to the result directory
        "config_file": "",          # The config file (e.g., reservation.yaml)
        "nodes":       {},          # Roles with nodes
        "phase":       "",          # Last phase that have been run
        "user":        "",          # User id for this job
        "cwd":         os.getcwd()  # Current Working Directory
    }

    env_path = os.path.join(resultdir, "env")

    if not os.path.exists(env_path):
        env['resultdir'] = resultdir
        _save_env(env)

    elif os.path.isfile(env_path):
        with open(env_path, "r") as f:
            env.update(yaml.load(f))
            logging.debug("Loaded environment %s", env_path)

        # Resets the configuration of the environment
        if os.path.isfile(env["config_file"]):
            with open(env["config_file"], "r") as f:
                env["config"].update(yaml.load(f))
                logging.debug("Reloaded config %s", env["config"])

    return env


def _save_env(env):
    """Saves one environment."""
    env_path = os.path.join(env['resultdir'], 'env')

    if os.path.isdir(env['resultdir']):
        with open(env_path, 'w') as f:
            yaml.dump(env, f)


def _set_resultdir(name=None):
    """Set or get the directory to store experiment results.

    Looks at the `name` and create the directory if it doesn't exist
    or returns it in other cases. If the name is `None`, then the
    function generates an unique name for the results directory.
    Finally, it links the directory to `SYMLINK_NAME`.

    :param name: file path to an existing directory. It could be
    weather an absolute or a relative to the current working
    directory.

    Returns the file path of the results directory.

    """
    # Compute file path of results directory
    resultdir_name = name or 'enos_' + datetime.today().isoformat()
    resultdir_path = os.path.abspath(resultdir_name)

    # Raise error if a related file exists
    if os.path.isfile(resultdir_path):
        raise EnosFilePathError(resultdir_path,
                                "Result directory cannot be created due "
                                "to existing file %s" % resultdir_path)

    # Create the result directory if it does not exist
    if not os.path.isdir(resultdir_path):
        os.mkdir(resultdir_path)
        logging.info('Generate results directory %s' % resultdir_path)

    # Symlink the result directory with the 'cwd/current' directory,
    # if this is not the cwd/current
    link_path = SYMLINK_NAME
    if not resultdir_path == link_path:
        if os.path.lexists(link_path):
            os.remove(link_path)
        try:
            os.symlink(resultdir_path, link_path)
            logging.info("Symlink %s to %s" % (resultdir_path, link_path))
        except OSError:
            # An harmless error can occur due to a race condition when
            # multiple regions are simultaneously deployed
            logging.warning("Symlink %s to %s failed" %
                            (resultdir_path, link_path))

    logging.info("Directory for experiment results is %s",
                 resultdir_path)

    return resultdir_path


enostasks = {}  # The map of all enos tasks indexed by their name


def enostask(doc):
    """Decorator for an Enos Task.

    This decorator lets you define a new Enos task and helps you
    manage the environment.

    """
    def decorator(fn):
        fn.__doc__ = doc

        @wraps(fn)
        def decorated(*args, **kwargs):
            logging.debug("Call task %s with args %s" %
                          (fn.__name__, kwargs))

            # Constructs the directory that will store the environment
            # (if it doesn't exists) and then put or load the
            # environment in it. --env may contains the directory name
            # or None.
            result_dir = _set_resultdir(kwargs.get("--env"))
            kwargs['env'] = _make_env(result_dir)

            # Proceeds with the function execution
            try:
                fn(*args, **kwargs)
            # Save the environment
            finally:
                _save_env(kwargs['env'])

        enostasks[fn.__name__] = decorated

        return decorated
    return decorator


def check_env(fn):
    """Decorator for an Enos Task.

    This decorator checks if an environment file exists.

    """
    @wraps(fn)
    def decorator(*args, **kwargs):
        # If no directory is provided, set the default one
        resultdir = kwargs.get('--env', SYMLINK_NAME)
        # Check if the env file exists
        env_path = os.path.join(resultdir, 'env')
        if not os.path.isfile(env_path):
            raise Exception("The file %s does not exist." % env_path)

        # Proceeds with the function execution
        return fn(*args, **kwargs)
    return decorator
