let isActive = false;

async function activate() {
  if (isActive) return;
  isActive = true;

  const images = document.querySelectorAll('img');
  const urls = [];

  images.forEach((img) => {
    if (img.offsetWidth < 20 || img.offsetHeight < 20) return;
    if (window.getComputedStyle(img).display === 'none') return;
    if (!img.src) return;

    img.classList.add('image-detector-active');
    urls.push(img.src);
  });

  if (urls.length > 0) {
    try {
      await fetch('http://127.0.0.1:8000/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls })
      });
    } catch (e) {
      console.error('server not running:', e);
    }
  }
}

function deactivate() {
  if (!isActive) return;
  isActive = false;

  document.querySelectorAll('.image-detector-active').forEach((img) => {
    img.classList.remove('image-detector-active');
  });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'activate') {
    activate().then(() => sendResponse({ status: 'activated' }));
    return true;
  } else if (request.action === 'deactivate') {
    deactivate();
    sendResponse({ status: 'deactivated' });
  }
});
