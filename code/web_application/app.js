"use strict";

// API endpoint used to create vulnerability reports.
const API_URL = "/api/vulnerability-reports";

// Closure that remembers the number of successful submissions.
const submissionCounter = (() => {
    let count = 0;

    return () => {
        count += 1;
        return count;
    };
})();

// Validate the fields that need browser-side checking.
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

// Listen for the form submission.
document
    .getElementById("vulnerabilityForm")
    .addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!validateForm()) {
            return;
        }

        // Collect the form values into one JavaScript object.
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

        // Convert the object to JSON and back to demonstrate JSON handling.
        const jsonString = JSON.stringify(formData);
        const parsedObject = JSON.parse(jsonString);

        // Extract selected values using object destructuring.
        const { packageName, submitterEmail } = parsedObject;

        console.log("Package name:", packageName);
        console.log("Submitter email:", submitterEmail);

        try {
            // Send the JSON data to the FastAPI POST endpoint.
            const response = await fetch(API_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(parsedObject)
            });

            const responseData = await response.json();

            // Display validation errors returned by FastAPI.
            if (!response.ok) {
                const errorMessage = responseData.detail
                    ? JSON.stringify(responseData.detail)
                    : "The report could not be submitted.";

                throw new Error(errorMessage);
            }

            // Count only successful backend submissions.
            const submissionCount = submissionCounter();

            console.log("Created API record:", responseData);
            console.log(
                "Successful submission count:",
                submissionCount
            );

            alert(
                `Vulnerability report submitted successfully! API ID: ${responseData.id}`
            );

            // Clear the form after a successful submission.
            document.getElementById("vulnerabilityForm").reset();
        } catch (error) {
            console.error("Submission error:", error);
            alert(`Submission failed: ${error.message}`);
        }
    });