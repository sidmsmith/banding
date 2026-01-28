const express = require('express');
const path = require('path');
const fs = require('fs');
const fetch = require('node-fetch');

const app = express();
app.use(express.json({ limit: '10mb' }));

// Serve static files from both root and public directory
// IMPORTANT: Static files must be served BEFORE the catch-all route
app.use(express.static(__dirname, { 
  extensions: ['html', 'css', 'js'],
  index: false // Don't serve index.html for directories
}));
app.use(express.static(path.join(__dirname, 'public')));

// Explicitly serve image files (before catch-all) - must come before catch-all route
app.get(/\.(png|jpg|jpeg|gif|svg|ico|webp)$/i, (req, res) => {
  // Try root directory first
  const rootPath = path.join(__dirname, req.path);
  console.log('Attempting to serve image:', req.path, 'from:', rootPath);
  
  if (fs.existsSync(rootPath)) {
    console.log('Image found at:', rootPath);
    return res.sendFile(rootPath);
  }
  // Try public directory
  const publicPath = path.join(__dirname, 'public', req.path);
  if (fs.existsSync(publicPath)) {
    console.log('Image found at:', publicPath);
    return res.sendFile(publicPath);
  }
  // Not found
  console.error('Image not found:', req.path, 'Tried:', rootPath, 'and', publicPath);
  res.status(404).json({ error: 'Image not found', path: req.path, tried: [rootPath, publicPath] });
});

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

// Catch-all for SPA routing (must be last, after all static file handlers)
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server on port ${PORT}`));
