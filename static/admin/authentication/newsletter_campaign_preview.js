(function () {
  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let index = 0; index < cookies.length; index += 1) {
      const cookie = cookies[index].trim();
      if (cookie.substring(0, name.length + 1) === `${name}=`) {
        return decodeURIComponent(cookie.substring(name.length + 1));
      }
    }
    return '';
  }

  function getFieldValue(name) {
    const field = document.querySelector(`[name="${name}"]`);
    return field ? field.value : '';
  }

  function initializeNewsletterPreview() {
    const previewFrame = document.getElementById('newsletter-email-preview');
    if (!previewFrame || !previewFrame.dataset.previewUrl) {
      return;
    }

    const fieldNames = [
      'subject',
      'preheader',
      'header_title',
      'header_subtitle',
      'body_html',
      'cta_text',
      'cta_url',
      'footer_note',
    ];
    const fields = fieldNames
      .map((name) => document.querySelector(`[name="${name}"]`))
      .filter(Boolean);
    let timeoutId = null;
    let abortController = null;

    function refreshPreview() {
      const payload = new FormData();
      fieldNames.forEach((name) => {
        payload.append(name, getFieldValue(name));
      });

      if (abortController) {
        abortController.abort();
      }
      abortController = new AbortController();

      fetch(previewFrame.dataset.previewUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: payload,
        signal: abortController.signal,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error('Preview request failed.');
          }
          return response.json();
        })
        .then((data) => {
          previewFrame.srcdoc = data.html || '';
        })
        .catch((error) => {
          if (error.name !== 'AbortError') {
            // Keep the last good preview visible when a transient request fails.
            console.error(error);
          }
        });
    }

    function scheduleRefresh() {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(refreshPreview, 350);
    }

    fields.forEach((field) => {
      field.addEventListener('input', scheduleRefresh);
      field.addEventListener('change', scheduleRefresh);
    });

    refreshPreview();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeNewsletterPreview);
  } else {
    initializeNewsletterPreview();
  }
})();
