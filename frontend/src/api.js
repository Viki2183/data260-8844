import axios from "axios";


const api = axios.create({
  baseURL: "http://localhost:8744",
  withCredentials: true,
});


export async function login(email, password) {
  const response = await api.post("/api/auth/login", {
    email,
    password,
  });

  return response.data;
}


export async function logout() {
  const response = await api.post("/api/auth/logout");
  return response.data;
}


export async function getCurrentUser() {
  const response = await api.get("/api/auth/me");
  return response.data;
}


export async function listReports(
  search = "",
  skip = 0,
  limit = 100,
) {
  const response = await api.get("/api/vulnerability-reports", {
    params: {
      ...(search ? { search } : {}),
      skip,
      limit,
    },
  });

  return response.data;
}


export async function getReport(id) {
  const response = await api.get(
    `/api/vulnerability-reports/${id}`,
  );

  return response.data;
}


export async function createReport(payload) {
  const response = await api.post(
    "/api/vulnerability-reports",
    payload,
  );

  return response.data;
}


export async function updateReport(id, payload) {
  const response = await api.put(
    `/api/vulnerability-reports/${id}`,
    payload,
  );

  return response.data;
}


export async function deleteReport(id) {
  const response = await api.delete(
    `/api/vulnerability-reports/${id}`,
  );

  return response.data;
}