"""Deployment selection for the local host.

The package records a target, a compose package, a release plan,
fail-closed service controls, the deployment checkpoint, and a
deployed-state check that refuses a live smoke. It does not create a
host, open a socket, push an image, or read a secret.
"""
