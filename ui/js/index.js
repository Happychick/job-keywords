var API_DOMAIN = "http://127.0.0.1:8000";
$(document).ready(function () {
    // make sure the spinner is hidden when the page loads
    $(".w-lightbox-spinner").hide();

    // when the form is submitted
    $('#email-form').submit(function () {
        // show the spinner
        $(".w-lightbox-spinner").show();

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
            $("#imageElement").show();
            $("#imageElement").attr("src", data.imageUrl);

            console.log("Skills found", data.skills);

            // show/hide the container with the "no items found" message
            if (data.skills.length) {
                $("#empty-div").hide();
            } else {
                $("#empty-div").show();
            }
        }).fail(function (data) { // if request fails
            console.log("error", data);
            $("#imageElement").hide();
        }).always(function () { // this function will always be executed
            $(".w-lightbox-spinner").hide(); // hide the spinner
        });

        return false; // prevent the form from submitting
    });
});