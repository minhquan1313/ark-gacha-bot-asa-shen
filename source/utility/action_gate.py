from source.utility import ark_runtime


def before_ark_action():
    """Pause game input until ARK is focused and its pause menu is closed."""
    ark_runtime.wait_until_ready()
