# DATA 260 Homework 5

## Project

Package Vulnerability Reporting Platform

## Purpose

Homework 5 integrates Redux Toolkit into the React frontend. The report list and report CRUD operations are managed through Redux state and asynchronous Redux thunks.

## Main Changes

- Connected report loading to Redux.
- Added Redux actions for create, update, and delete.
- Added package ID to the create and update forms.
- Added affected versions count.
- Updated the backend to save affected-version counts.
- Connected the delete page to the Redux delete thunk.
- Verified the frontend production build with Vite.

## Technology

- React
- Redux Toolkit
- Axios
- Vite
- FastAPI
- SQLAlchemy
- MySQL

## Running the Application

Start the backend in one PowerShell window:

    cd C:\Projects\data260-8844\code\web_application
    & C:\Projects\data260-8844\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8744

Start the frontend in another PowerShell window:

    cd C:\Projects\data260-8844\frontend
    npm run dev

Open the frontend in a browser:

    http://localhost:5173

## Verification

The following workflows were tested successfully:

1. User login.
2. Loading vulnerability reports.
3. Creating a vulnerability report.
4. Updating a report.
5. Saving affected versions count.
6. Deleting a report.
7. Building the frontend with `npm run build`.

## Submission

- Branch: `hw5-development`
- Git tag: `hw5`
- Report folder: `reports/hw05`