jQuery(function ($) {
    $(document).ready(function () { //function will wait for the page to fully load before executing
        let deadline = $("#id_deadline")
        if ($("#id_question_required_0, #id_question_required_1").is(':checked')) {
            deadline.attr("disabled", true);
            deadline.attr("required", false);
        }
        $("#id_question_required_2, #id_question_required_3").click(function () {
            deadline.attr("disabled", false);
            deadline.attr("required", true);
        });
        $("#id_question_required_0, #id_question_required_1").click(function () {
            deadline.val("");
            deadline.attr("disabled", true);
            deadline.attr("required", false);
        });
    });
})
