const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Serve static files from the static folder
app.use('/', express.static(path.join(__dirname, 'static')));

// Also serve repository root to allow favicon reference
app.use('/favicon.ico', express.static(path.join(__dirname, '..', 'favicon.ico')));

app.listen(PORT, () => {
  console.log(`Frontend server running on http://localhost:${PORT}`);
});
