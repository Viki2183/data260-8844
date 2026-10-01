import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import {
  createReport,
  deleteReport,
  listReports,
  updateReport,
} from "../../api";

function getErrorMessage(error) {
  return (
    error.response?.data?.detail ||
    error.message ||
    "The request could not be completed."
  );
}


// Fetch the current report list from FastAPI.
export const fetchReports = createAsyncThunk(
  "reports/fetchReports",
  async (
    { search = "", skip = 0, limit = 100 } = {},
    { rejectWithValue },
  ) => {
    try {
      return await listReports(search, skip, limit);
    } catch (error) {
      return rejectWithValue(getErrorMessage(error));
    }
  },
);


// Create a new vulnerability report.
export const addReport = createAsyncThunk(
  "reports/addReport",
  async (payload, { rejectWithValue }) => {
    try {
      return await createReport(payload);
    } catch (error) {
      return rejectWithValue(getErrorMessage(error));
    }
  },
);


// Update an existing vulnerability report.
export const editReport = createAsyncThunk(
  "reports/editReport",
  async ({ id, payload }, { rejectWithValue }) => {
    try {
      return await updateReport(id, payload);
    } catch (error) {
      return rejectWithValue(getErrorMessage(error));
    }
  },
);


// Delete a vulnerability report.
export const removeReport = createAsyncThunk(
  "reports/removeReport",
  async (id, { rejectWithValue }) => {
    try {
      await deleteReport(id);
      return Number(id);
    } catch (error) {
      return rejectWithValue(getErrorMessage(error));
    }
  },
);


const initialState = {
  items: [],
  status: "idle",
  error: null,
};


const reportsSlice = createSlice({
  name: "reports",
  initialState,
  reducers: {
  clearReportError(state) {
    state.error = null;
  },

  clearReports(state) {
    state.items = [];
    state.status = "idle";
    state.error = null;
  },
},
  extraReducers: (builder) => {
    builder
      .addCase(fetchReports.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(fetchReports.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.items = action.payload;
      })
      .addCase(fetchReports.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload || "Unable to load reports.";
      })

      .addCase(addReport.pending, (state) => {
        state.status = "saving";
        state.error = null;
      })
      .addCase(addReport.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.items.push(action.payload);
      })
      .addCase(addReport.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload || "Unable to create the report.";
      })

      .addCase(editReport.pending, (state) => {
        state.status = "saving";
        state.error = null;
      })
      .addCase(editReport.fulfilled, (state, action) => {
        state.status = "succeeded";

        const index = state.items.findIndex(
          (report) => report.id === action.payload.id,
        );

        if (index !== -1) {
          state.items[index] = action.payload;
        }
      })
      .addCase(editReport.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload || "Unable to update the report.";
      })

      .addCase(removeReport.pending, (state) => {
        state.status = "saving";
        state.error = null;
      })
      .addCase(removeReport.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.items = state.items.filter(
          (report) => report.id !== action.payload,
        );
      })
      .addCase(removeReport.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload || "Unable to delete the report.";
      });
  },
});


export const {
  clearReportError,
  clearReports,
} = reportsSlice.actions;

export default reportsSlice.reducer;