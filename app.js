"use strict";

// Closure that remembers the number of successful submissions.
const submissionCounter = (() => {
    let count = 0;

    return () => {
        count += 1;
        return count;
    };
})();

// Arrow function used to validate the description and terms checkbox.
const validateForm = () => {
    const description = document
        .getElementById("vulnerabilityDescription")
        .value
        .trim();

    const termsAccepted =
        document.getElementById("termsAccepted").checked;

    if (description.length <= 25) {
        alert(
            "The vulnerability description must contain more than 25 characters."
        );
        return false;
    }

    if (!termsAccepted) {
        alert(
            "You must agree to the terms and conditions before submitting."
        );
        return false;
    }

    return true;
};

document
    .getElementById("vulnerabilityForm")
    .addEventListener("submit", (event) => {
        event.preventDefault();

        if (!validateForm()) {
            return;
        }

        const formData = {
            packageName: document
                .getElementById("packageName")
                .value
                .trim(),

            vulnerabilityId: document
                .getElementById("vulnerabilityId")
                .value
                .trim(),

            submitterEmail: document
                .getElementById("submitterEmail")
                .value
                .trim(),

            vulnerabilityDescription: document
                .getElementById("vulnerabilityDescription")
                .value
                .trim(),

            severity: document.getElementById("severity").value,

            termsAccepted:
                document.getElementById("termsAccepted").checked
        };

        // Convert the form object into a JSON string.
        const jsonString = JSON.stringify(formData);

        console.log("JSON string:");
        console.log(jsonString);

        // Convert the JSON string back into a JavaScript object.
        const parsedObject = JSON.parse(jsonString);

        // Extract the primary field and email using object destructuring.
        const { packageName, submitterEmail } = parsedObject;

        console.log("Package name:", packageName);
        console.log("Submitter email:", submitterEmail);

        // Add the current date and time using the spread operator.
        const updatedObject = {
            ...parsedObject,
            submissionDate: new Date().toISOString()
        };

        console.log("Updated object:");
        console.log(updatedObject);

        // Increase and display the closure-based submission count.
        const submissionCount = submissionCounter();

        console.log("Successful submission count:", submissionCount);

        alert("Vulnerability report submitted successfully!");
    });