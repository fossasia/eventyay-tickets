(function ($) {

    $(document).ready(function () {
        moveElement('send_grid_api_key', 'email_vendor', 0)
        moveElement('smtp_host', 'email_vendor', 1)
        moveElement('smtp_port', 'email_vendor', 1)
        moveElement('smtp_username', 'email_vendor', 1)
        moveElement('smtp_password', 'email_vendor', 1)
        moveElement('smtp_use_tls', 'email_vendor', 1)
        moveElement('smtp_use_ssl', 'email_vendor', 1)
    })

    /**
     * Find HTML element.
     * @param {*} el - The element - used to find it parent
     * @param {*} return_parent - Boolean variable used to decide whether to return the found element or its parent node.
     * @param {*} max - Maximun steps, return null  if the maximum steps are reached without finding a matching element.
     * @returns 
     */
    function findParent(el, return_parent = false, max = 0) {
        if (max > 5) return null;
        if (el.parentNode.className == 'form-group') {

            return return_parent ? el.parentNode : el
        } else {
            return findParent(el.parentNode, return_parent, max + 1)
        }
    }

    /**
     * Moves the specified HTML element to become a child of a radio button element.
     * @param {*} el_name - The element name to be moved.
     * @param {*} target - The radio button name - where `el_name` will be appended.
     * @param {*} target_pos - Position of radio button in radio button group.
     */
    function moveElement(el_name, target, target_pos) {
        try {
            var el = document.getElementsByName(el_name)[0]
            var rootOfGroup = findParent(el, true)
            var des = document.getElementsByName(target)[target_pos]
            var rootOfDes = des.parentNode.parentNode
            console.log(rootOfDes, rootOfGroup)
            $(rootOfGroup).detach();
            $(rootOfDes).append(rootOfGroup)
        } catch (e) {
            console.error("==================", e)
        }

    }
})(jQuery);