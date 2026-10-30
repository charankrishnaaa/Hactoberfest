// Bolo API Configuration
// This is the ONLY place to configure backend connectivity.

const LOCAL_API = "http://127.0.0.1:8000";
const PROD_API = "";   // TODO: paste the deployed backend URL here, no trailing slash

window.BOLO_API = (location.hostname === "localhost" || location.hostname === "127.0.0.1") ? LOCAL_API : PROD_API;
