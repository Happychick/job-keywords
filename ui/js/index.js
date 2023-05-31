var API_DOMAIN = "http://127.0.0.1:8000";
$(document).ready(function () {
    // make sure the spinner is hidden when the page loads
    $("#spinner-div").hide();

    // when the form is submitted
    $('#email-form').submit(function () {
        if (!$('#name-2').val()) {
            return false; // prevent the form from submitting if the input field is empty
        }

        // show the spinner
        $("#spinner-div").show();

        // make the API call
        $.ajax({
            url: API_DOMAIN + "/search/tasks",
            method: "POST",
            context: document.body,
            contentType: "application/json",
            data: JSON.stringify({
                "searchToken": $('#name-2').val() // Grab the value from the input field
            })
        }).done(function (data) { // if request is successful
            // show the image from response
            $("#not-empty-div").show();
            $("#imageElement").attr("src", data.imageUrl);
            $("#imageElementLink").attr("href", data.imageUrl);

            $(".question_block").show();

            $("#skill-list").html(""); // clear the list
            $("#skill-list").append("<tr class='header'><th>Skill</th><td>Occurrences</td></tr>"); // add the table header
            data.skills.forEach(function (skill, index) { // iterate over the skills
                if (index > 30) {
                    return; // show only the first 30 skills
                }
                $("#skill-list").append("<tr><th>" + skill.name + "</th><td>" + skill.occurrences + "</td></tr>"); // add each skill to the list
            });

            // show/hide the container with the "no items found" message
            if (data.skills.length) {
                $("#empty-div").hide();
                $("#skill-list").show();
                $("#skill-list-div").show();
            } else {
                $("#empty-div").show();
                $("#skill-list").hide();
                $("#skill-list-div").hide();
            }
        }).fail(function (data) { // if request fails
            $("#not-empty-div").hide();
            $("#skill-list").html("");
            $("#skill-list").hide();
            $("#skill-list-div").hide();
        }).always(function () { // this function will always be executed
            $("#spinner-div").hide(); // hide the spinner
            $("#feedback-div").show(); // show the feedback form
        });

        return false; // prevent the form from submitting
    });

    $('#feedback-form').submit(function () {
        if (!$('#feedbackMessage').val()) {
            return false; // prevent the form from submitting if the input field is empty
        }

        // make the API call
        $.ajax({
            url: API_DOMAIN + "/feedback",
            method: "POST",
            context: document.body,
            contentType: "application/json",
            data: JSON.stringify({
                "message": $('#feedbackMessage').val(), // Grab the value from the input field
                "searchText": $('#name-2').val() // Grab the value from the input field
            })
        }).done(function (data) { // if request is successful
            // show the image from response
            $("#feedbackMessage").val("");
            $("#feedbackMessage").hide("");

            $('#feedback-form').find('input[type="submit"]').hide();
            $('#feedbackSent').show();
        }).fail(function (data) { // if request fails
            $('#feedbackNotSent').show();
        })

        return false; // prevent the form from submitting
    });

});