"use strict";

// The backend endpoint used by the webpage.
const API_URL = "/api/vulnerability-reports";

// Closure that remembers successful create and update operations.
const submissionCounter = (() => {
    let count = 0;

    return () => {
        count += 1;
        return count;
    };
})();

// Store the current search text for refreshes after CRUD operations.
let currentSearch = "";

// Get frequently used page elements.
const form = document.getElementById("vulnerabilityForm");
const searchForm = document.getElementById("searchForm");
const searchInput = document.getElementById("searchInput");
const reportsList = document.getElementById("reportsList");
const loadingState = document.getElementById("loadingState");
const emptyState = document.getElementById("emptyState");
const errorState = document.getElementById("errorState");
const reportIdInput = document.getElementById("reportId");
const formHeading = document.getElementById("form-heading");
const submitButton = document.getElementById("submitButton");
const cancelEditButton = document.getElementById("cancelEditButton");

// Show or hide a message area.
const setStateVisibility = (element, isVisible) => {
    element.classList.toggle("hidden", !isVisible);
};

// Display an error message to the user.
const showError = (message) => {
    errorState.textContent = message;
    setStateVisibility(errorState, true);
};

// Clear the current error message.
const clearError = () => {
    errorState.textContent = "";
    setStateVisibility(errorState, false);
};

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

// Collect the form values into one object.
const getFormData = () => ({
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
});

// Escape text before placing API values into HTML.
const escapeHtml = (value) => {
    const temporaryElement = document.createElement("div");
    temporaryElement.textContent = value ?? "";
    return temporaryElement.innerHTML;
};

// Display a report safely as a report card.
const createReportCard = (report) => `
    <article class="report-card">
        <h3>${escapeHtml(report.packageName)}</h3>

        <p>
            <strong>Report ID:</strong>
            ${escapeHtml(String(report.id))}
        </p>

        <p>
            <strong>Vulnerability ID:</strong>
            ${escapeHtml(report.vulnerabilityId)}
        </p>

        <p>
            <strong>Description:</strong>
            ${escapeHtml(report.vulnerabilityDescription)}
        </p>

        <p>
            <strong>Severity:</strong>
            ${escapeHtml(report.severity)}
        </p>

        <p>
            <strong>Submitter:</strong>
            ${escapeHtml(report.submitterEmail)}
        </p>

        <p>
            <strong>Submitted:</strong>
            ${escapeHtml(report.submissionDate)}
        </p>

        <div class="report-actions">
            <button
                type="button"
                class="edit-button"
                data-id="${report.id}"
            >
                Edit
            </button>

            <button
                type="button"
                class="delete-button secondary-button"
                data-id="${report.id}"
            >
                Delete
            </button>
        </div>
    </article>
`;

// Render the reports returned by the API.
const renderReports = (reports) => {
    reportsList.innerHTML = "";

    if (!reports || reports.length === 0) {
        setStateVisibility(emptyState, true);
        return;
    }

    setStateVisibility(emptyState, false);

    reportsList.innerHTML = reports
        .map((report) => createReportCard(report))
        .join("");
};

// Load all reports or search results.
const loadReports = async (searchText = "") => {
    currentSearch = searchText.trim();

    setStateVisibility(loadingState, true);
    setStateVisibility(emptyState, false);
    clearError();

    const requestUrl = currentSearch
        ? `${API_URL}?search=${encodeURIComponent(currentSearch)}`
        : API_URL;

    try {
        const response = await fetch(requestUrl);

        if (!response.ok) {
            throw new Error(`The server returned status ${response.status}.`);
        }

        const reports = await response.json();
        renderReports(reports);
    } catch (error) {
        reportsList.innerHTML = "";
        setStateVisibility(emptyState, false);
        showError(`Unable to load reports: ${error.message}`);
    } finally {
        setStateVisibility(loadingState, false);
    }
};

// Fill the form with an existing report for editing.
const startEditing = async (reportId) => {
    clearError();

    try {
        const response = await fetch(`${API_URL}/${reportId}`);

        if (!response.ok) {
            throw new Error(`The server returned status ${response.status}.`);
        }

        const report = await response.json();

        reportIdInput.value = report.id;
        document.getElementById("packageName").value = report.packageName;
        document.getElementById("vulnerabilityId").value =
            report.vulnerabilityId;
        document.getElementById("submitterEmail").value =
            report.submitterEmail;
        document.getElementById("vulnerabilityDescription").value =
            report.vulnerabilityDescription;
        document.getElementById("severity").value = report.severity;
        document.getElementById("termsAccepted").checked =
            report.termsAccepted;

        formHeading.textContent = `Edit Report ${report.id}`;
        submitButton.textContent = "Update Vulnerability Report";
        setStateVisibility(cancelEditButton, true);

        form.scrollIntoView({ behavior: "smooth" });
    } catch (error) {
        showError(`Unable to load report for editing: ${error.message}`);
    }
};

// Return the form to create mode.
const resetFormMode = () => {
    form.reset();
    reportIdInput.value = "";
    formHeading.textContent = "Submit a Vulnerability Report";
    submitButton.textContent = "Submit Vulnerability Report";
    setStateVisibility(cancelEditButton, false);
};

// Delete one report.
const deleteReport = async (reportId) => {
    const confirmed = window.confirm(
        `Delete vulnerability report ${reportId}?`
    );

    if (!confirmed) {
        return;
    }

    clearError();

    try {
        const response = await fetch(`${API_URL}/${reportId}`, {
            method: "DELETE"
        });

        if (!response.ok) {
            throw new Error(`The server returned status ${response.status}.`);
        }

        alert(`Vulnerability report ${reportId} was deleted.`);
        await loadReports(currentSearch);
    } catch (error) {
        showError(`Unable to delete report: ${error.message}`);
    }
};

// Submit a new report or update an existing report.
form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!validateForm()) {
        return;
    }

    clearError();

    const formData = getFormData();
    const editingId = reportIdInput.value;
    const isEditing = Boolean(editingId);

    const requestUrl = isEditing
        ? `${API_URL}/${editingId}`
        : API_URL;

    const requestMethod = isEditing ? "PUT" : "POST";

    // Convert the object to JSON and back to demonstrate JSON handling.
    const jsonString = JSON.stringify(formData);
    const parsedObject = JSON.parse(jsonString);

    // Extract selected values using object destructuring.
    const { packageName, submitterEmail } = parsedObject;

    console.log("Package name:", packageName);
    console.log("Submitter email:", submitterEmail);

    submitButton.disabled = true;

    try {
        const response = await fetch(requestUrl, {
            method: requestMethod,
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(parsedObject)
        });

        const responseData = await response.json();

        if (!response.ok) {
            const errorMessage = responseData.detail
                ? JSON.stringify(responseData.detail)
                : "The report could not be submitted.";

            throw new Error(errorMessage);
        }

        const submissionCount = submissionCounter();

        console.log("API response:", responseData);
        console.log(
            "Successful create/update count:",
            submissionCount
        );

        const actionText = isEditing ? "updated" : "created";

        alert(
            `Vulnerability report ${actionText} successfully! API ID: ${responseData.id}`
        );

        resetFormMode();
        await loadReports(currentSearch);
    } catch (error) {
        console.error("Submission error:", error);
        showError(`Submission failed: ${error.message}`);
    } finally {
        submitButton.disabled = false;
    }
});

// Search by package name or vulnerability ID.
searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await loadReports(searchInput.value);
});

// Clear the search and show every report.
document
    .getElementById("clearSearchButton")
    .addEventListener("click", async () => {
        searchInput.value = "";
        await loadReports();
    });

// Start editing when an Edit button is clicked.
reportsList.addEventListener("click", async (event) => {
    const editButton = event.target.closest(".edit-button");

    if (editButton) {
        await startEditing(editButton.dataset.id);
        return;
    }

    const deleteButton = event.target.closest(".delete-button");

    if (deleteButton) {
        await deleteReport(deleteButton.dataset.id);
    }
});

// Cancel editing and return to create mode.
cancelEditButton.addEventListener("click", () => {
    resetFormMode();
});

// Load the initial report list when the page opens.
loadReports();