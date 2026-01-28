const express = require('express');
const path = require('path');
const fs = require('fs');
const fetch = require('node-fetch');

const app = express();
app.use(express.json({ limit: '10mb' }));

// Serve static files from both root and public directory
app.use(express.static(__dirname));
app.use(express.static(path.join(__dirname, 'public')));

// Proxy all /api calls to Flask (running on localhost:5000 during dev)
app.post('/api/:action', async (req, res) => {
  const url = process.env.VERCEL ? `https://${process.env.VERCEL_URL}/api/${req.params.action}` : 'http://localhost:5000/api/' + req.params.action;
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body)
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Handle image files explicitly (for Vercel serverless)
app.get(/\.(png|jpg|jpeg|gif|svg|ico|webp)$/i, (req, res, next) => {
  // Skip favicon.ico - let it 404 gracefully
  if (req.path === '/favicon.ico') {
    return res.status(404).send('Not found');
  }
  
  // Try public directory first (Vercel serves this automatically)
  const publicPath = path.join(__dirname, 'public', req.path);
  if (fs.existsSync(publicPath)) {
    return res.sendFile(publicPath, (err) => {
      if (err) {
        console.error('Error serving file from public:', err);
        res.status(404).send('File not found');
      }
    });
  }
  
  // Fallback to root directory
  const rootPath = path.join(__dirname, req.path);
  res.sendFile(rootPath, (err) => {
    if (err) {
      console.error('Error serving static file:', err);
      res.status(404).send('File not found');
    }
  });
});

// Catch-all for SPA routing (must be last)
// Use regex pattern instead of '*' to avoid path-to-regexp errors on Vercel
app.get(/^(?!\/api).*$/, (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server on port ${PORT}`));
