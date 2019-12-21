import os
import time

from django.utils import translation


def screenshot(client, name, scroll=True):
    time.sleep(1)
    if translation.get_language() != "en":
        p = name.rsplit(".", 1)
        p.insert(1, translation.get_language())
        name = ".".join(p)
    os.makedirs(os.path.join("screens", os.path.dirname(name)), exist_ok=True)
    if not scroll:
        client.save_screenshot(os.path.join("screens", name))
        return
    original_size = client.get_window_size()
    required_width = client.execute_script(
        "return document.body.parentNode.scrollWidth"
    )
    required_height = client.execute_script(
        "return document.body.parentNode.scrollHeight"
    )
    client.set_window_size(required_width, required_height)
    path = os.path.join("screens", name)
    client.find_element_by_tag_name("body").screenshot(path)
    client.set_window_size(original_size["width"], original_size["height"])
