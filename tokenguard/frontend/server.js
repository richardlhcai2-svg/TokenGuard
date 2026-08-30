const { createServer } = require("http");
const next = require("next");

const dev = process.env.NODE_ENV !== "production";
const app = next({ dev });
const handle = app.getRequestHandler();

const API_TARGET = process.env.API_PROXY_TARGET || "http://localhost:8002";

app.prepare().then(() => {
  createServer(async (req, res) => {
    // Proxy API requests to backend
    if (req.url.startsWith("/api/v1/") || req.url.startsWith("/internal/")) {
      const http = require("http");
      const { URL } = require("url");
      const apiUrl = new URL(req.url, API_TARGET);

      const options = {
        hostname: apiUrl.hostname.replace("http:", "").replace("https:", ""),
        port: apiUrl.port || (apiUrl.protocol === "https:" ? 443 : 80),
        path: apiUrl.pathname + apiUrl.search,
        method: req.method,
        headers: req.headers,
      };

      const proxyReq = http.request(options, (proxyRes) => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      });

      proxyReq.on("error", (e) => {
        console.error("Proxy error:", e.message);
        res.writeHead(502);
        res.end("Bad Gateway");
      });

      req.pipe(proxyReq);
      return;
    }

    handle(req, res);
  }).listen(3000, (err) => {
    if (err) throw err;
    console.log(`> Ready on http://localhost:3000`);
  });
});
