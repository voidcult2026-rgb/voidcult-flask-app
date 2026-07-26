/* admin.js — drag-and-drop image dropzones, dynamic size/color rows, and
   checkout payment button wiring for the admin product form. */
(function () {
  document.querySelectorAll('.dropzone').forEach(zone => {
    const inputId = zone.dataset.input;
    const input = inputId ? document.getElementById(inputId) : null;
    if (!input) return;
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag');
      input.files = e.dataTransfer.files;
      previewFiles(input, zone.dataset.preview);
    });
    input.addEventListener('change', () => previewFiles(input, zone.dataset.preview));
  });

  function previewFiles(input, previewId) {
    if (!previewId) return;
    const wrap = document.getElementById(previewId);
    if (!wrap) return;
    [...input.files].forEach(file => {
      if (!file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = ev => {
        const div = document.createElement('div');
        div.className = 'th';
        div.innerHTML = `<img src="${ev.target.result}">`;
        wrap.appendChild(div);
      };
      reader.readAsDataURL(file);
    });
  }

  // Dynamic size/color chip rows on the product form
  function addRow(containerId, template) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'chip-row';
    div.innerHTML = template;
    container.appendChild(div);
    div.querySelector('.remove-row').addEventListener('click', () => div.remove());
  }
  const addSizeBtn = document.getElementById('add-size-row');
  if (addSizeBtn) addSizeBtn.addEventListener('click', () => addRow('size-rows',
    `<input name="size_name[]" placeholder="Size (e.g. M)"><input name="size_stock[]" type="number" placeholder="Stock" style="max-width:100px;"><button type="button" class="remove-row">✕</button>`
  ));
  const addColorBtn = document.getElementById('add-color-row');
  if (addColorBtn) addColorBtn.addEventListener('click', () => addRow('color-rows',
    `<input name="color_name[]" placeholder="Color name"><input name="color_hex[]" type="color" value="#1a1a1a" style="max-width:60px;padding:2px;"><button type="button" class="remove-row">✕</button>`
  ));
  document.querySelectorAll('.remove-row').forEach(b => b.addEventListener('click', () => b.parentElement.remove()));

  // Product image delete (AJAX)
  document.querySelectorAll('.delete-image-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const imageId = btn.dataset.imageId;
      const csrf = document.querySelector('input[name=csrf_token]').value;
      fetch(`/admin/products/image/${imageId}/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'csrf_token=' + encodeURIComponent(csrf)
      }).then(() => btn.closest('.th').remove());
    });
  });
})();
