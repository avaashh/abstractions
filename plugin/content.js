let isActive = false;

async function activate() {
  if (isActive) return;
  isActive = true;

  const images = document.querySelectorAll('img');
  const urls = [];
  const captionEls = [];

  images.forEach((img) => {
    if (img.offsetWidth < 20 || img.offsetHeight < 20) return;
    if (window.getComputedStyle(img).display === 'none') return;
    if (!img.src) return;
    if (img.closest('.image-detector-wrapper')) return;

    // Create wrapper container
    const wrapper = document.createElement('div');
    wrapper.className = 'image-detector-wrapper';

    // Create caption element
    const caption = document.createElement('div');
    caption.className = 'image-detector-caption';
    caption.textContent = 'Loading...';

    // Wrap the image
    img.parentNode.insertBefore(wrapper, img);
    wrapper.appendChild(img);
    wrapper.appendChild(caption);

    img.classList.add('image-detector-active');
    urls.push(img.src);
    captionEls.push(caption);
  });

  if (urls.length > 0) {
    try {
      const response = await fetch('http://127.0.0.1:8000/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls })
      });
      const data = await response.json();

      data.results.forEach((result, i) => {
        const el = captionEls[i];
        if (!el) return;

        const description = result.description || 'No description available.';
        const isMeme = !!result.is_meme;
        const confidence = typeof result.confidence === 'number'
          ? ` (${Math.round(result.confidence * 100)}%)`
          : '';

        const label = document.createElement('div');
        label.className = 'image-detector-label';
        label.textContent = isMeme ? `MEME${confidence}` : `NOT A MEME${confidence}`;

        const body = document.createElement('div');
        body.className = 'image-detector-body';
        body.textContent = description;

        el.textContent = '';
        el.appendChild(label);
        el.appendChild(body);

        const wrapper = el.parentNode;
        if (wrapper) {
          wrapper.classList.toggle('image-detector-meme', isMeme);
          wrapper.classList.toggle('image-detector-not-meme', !isMeme);
        }
      });
    } catch (e) {
      console.error('server not running:', e);
      captionEls.forEach((el) => {
        el.textContent = 'Failed to load caption';
      });
    }
  }
}

function deactivate() {
  if (!isActive) return;
  isActive = false;

  document.querySelectorAll('.image-detector-wrapper').forEach((wrapper) => {
    const img = wrapper.querySelector('img');
    if (img) {
      img.classList.remove('image-detector-active');
      wrapper.parentNode.insertBefore(img, wrapper);
    }
    wrapper.remove();
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
