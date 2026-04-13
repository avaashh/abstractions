let active = false;

document.getElementById('toggle').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab) return;

  const action = active ? 'deactivate' : 'activate';

  try {
    await chrome.tabs.sendMessage(tab.id, { action });
    active = !active;
    document.getElementById('toggle').textContent = active ? 'clear detection' : 'detect images';
  } catch (e) {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js']
    });
    await chrome.scripting.insertCSS({
      target: { tabId: tab.id },
      files: ['styles.css']
    });
    await chrome.tabs.sendMessage(tab.id, { action: 'activate' });
    active = true;
    document.getElementById('toggle').textContent = 'clear detection';
  }
});
