/**
 * Fixed-frame crop: frame stays put; drag/zoom the image to fit inside.
 * Output is exactly options.width × options.height pixels.
 * No Cropper.js dependency.
 */
(function (global) {
  'use strict';

  var modalEl = null;
  var stageEl = null;
  var frameEl = null;
  var imgEl = null;
  var hintEl = null;
  var pending = null;
  var state = null;
  var drag = null;

  function ensureModal() {
    if (modalEl) return modalEl;
    modalEl = document.createElement('div');
    modalEl.id = 'admImageCropModal';
    modalEl.className = 'adm-crop-modal';
    modalEl.setAttribute('role', 'dialog');
    modalEl.setAttribute('aria-modal', 'true');
    modalEl.innerHTML =
      '<div class="adm-crop-dialog">' +
      '  <div class="adm-crop-header">' +
      '    <strong id="admCropTitle">Crop image</strong>' +
      '    <button type="button" class="adm-crop-close" id="admCropCancelX" aria-label="Close">&times;</button>' +
      '  </div>' +
      '  <div class="adm-crop-stage" id="admCropStage">' +
      '    <div class="adm-crop-frame" id="admCropFrame">' +
      '      <img id="admCropImage" alt="" draggable="false">' +
      '      <div class="adm-crop-frame-border" aria-hidden="true"></div>' +
      '    </div>' +
      '  </div>' +
      '  <div class="adm-crop-toolbar">' +
      '    <button type="button" class="btn btn-outline-secondary btn-sm" id="admCropZoomOut" title="Zoom out">−</button>' +
      '    <button type="button" class="btn btn-outline-secondary btn-sm" id="admCropZoomIn" title="Zoom in">+</button>' +
      '    <button type="button" class="btn btn-outline-secondary btn-sm" id="admCropReset" title="Reset">Reset</button>' +
      '  </div>' +
      '  <div class="adm-crop-hint" id="admCropHint"></div>' +
      '  <div class="adm-crop-actions">' +
      '    <button type="button" class="btn btn-outline-secondary btn-sm" id="admCropCancel">Cancel</button>' +
      '    <button type="button" class="btn btn-primary btn-sm" id="admCropApply">Use this crop</button>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(modalEl);
    stageEl = modalEl.querySelector('#admCropStage');
    frameEl = modalEl.querySelector('#admCropFrame');
    imgEl = modalEl.querySelector('#admCropImage');
    hintEl = modalEl.querySelector('#admCropHint');

    modalEl.querySelector('#admCropCancel').addEventListener('click', cancelCrop);
    modalEl.querySelector('#admCropCancelX').addEventListener('click', cancelCrop);
    modalEl.querySelector('#admCropApply').addEventListener('click', applyCrop);
    modalEl.querySelector('#admCropZoomIn').addEventListener('click', function () { zoomBy(1.12); });
    modalEl.querySelector('#admCropZoomOut').addEventListener('click', function () { zoomBy(1 / 1.12); });
    modalEl.querySelector('#admCropReset').addEventListener('click', function () {
      if (state) fitImage(true);
    });
    modalEl.addEventListener('click', function (e) {
      if (e.target === modalEl) cancelCrop();
    });

    frameEl.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);
    stageEl.addEventListener('wheel', onWheel, { passive: false });

    return modalEl;
  }

  function naturalSize() {
    return {
      w: imgEl.naturalWidth || 0,
      h: imgEl.naturalHeight || 0,
    };
  }

  function applyTransform() {
    if (!state) return;
    imgEl.style.width = state.dispW + 'px';
    imgEl.style.height = state.dispH + 'px';
    imgEl.style.transform = 'translate(' + state.x + 'px,' + state.y + 'px)';
  }

  function clampPosition() {
    if (!state) return;
    var fw = state.frameW;
    var fh = state.frameH;
    // Image must always cover the frame
    var minX = fw - state.dispW;
    var minY = fh - state.dispH;
    if (state.dispW <= fw) state.x = (fw - state.dispW) / 2;
    else state.x = Math.min(0, Math.max(minX, state.x));
    if (state.dispH <= fh) state.y = (fh - state.dispH) / 2;
    else state.y = Math.min(0, Math.max(minY, state.y));
  }

  function fitImage(resetZoom) {
    var nat = naturalSize();
    if (!nat.w || !nat.h || !state) return;
    var fw = state.frameW;
    var fh = state.frameH;
    // Cover the frame (like object-fit: cover)
    var scale = Math.max(fw / nat.w, fh / nat.h);
    state.scale = scale;
    state.dispW = nat.w * scale;
    state.dispH = nat.h * scale;
    state.x = (fw - state.dispW) / 2;
    state.y = (fh - state.dispH) / 2;
    if (!resetZoom) {
      /* already set */
    }
    clampPosition();
    applyTransform();
  }

  function zoomBy(factor) {
    if (!state) return;
    var nat = naturalSize();
    var fw = state.frameW;
    var fh = state.frameH;
    var minScale = Math.max(fw / nat.w, fh / nat.h);
    var maxScale = minScale * 6;
    var cx = fw / 2;
    var cy = fh / 2;
    // Keep the point under frame center stable
    var imgCx = (cx - state.x) / state.dispW;
    var imgCy = (cy - state.y) / state.dispH;
    var next = Math.min(maxScale, Math.max(minScale, state.scale * factor));
    state.scale = next;
    state.dispW = nat.w * next;
    state.dispH = nat.h * next;
    state.x = cx - imgCx * state.dispW;
    state.y = cy - imgCy * state.dispH;
    clampPosition();
    applyTransform();
  }

  function onPointerDown(e) {
    if (!state || e.button !== 0) return;
    e.preventDefault();
    frameEl.setPointerCapture(e.pointerId);
    drag = {
      id: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      origX: state.x,
      origY: state.y,
    };
    frameEl.classList.add('is-dragging');
  }

  function onPointerMove(e) {
    if (!drag || !state || e.pointerId !== drag.id) return;
    e.preventDefault();
    state.x = drag.origX + (e.clientX - drag.startX);
    state.y = drag.origY + (e.clientY - drag.startY);
    clampPosition();
    applyTransform();
  }

  function onPointerUp(e) {
    if (!drag || e.pointerId !== drag.id) return;
    try { frameEl.releasePointerCapture(e.pointerId); } catch (err) {}
    drag = null;
    frameEl.classList.remove('is-dragging');
  }

  function onWheel(e) {
    if (!state || !modalEl.classList.contains('is-open')) return;
    e.preventDefault();
    zoomBy(e.deltaY < 0 ? 1.08 : 1 / 1.08);
  }

  function layoutFrame() {
    if (!pending || !stageEl || !frameEl) return;
    var ratio = pending.width / pending.height;
    var stageW = stageEl.clientWidth;
    var stageH = stageEl.clientHeight;
    var pad = 24;
    var maxW = stageW - pad * 2;
    var maxH = stageH - pad * 2;
    var frameW;
    var frameH;
    if (maxW / maxH > ratio) {
      frameH = maxH;
      frameW = frameH * ratio;
    } else {
      frameW = maxW;
      frameH = frameW / ratio;
    }
    frameEl.style.width = Math.round(frameW) + 'px';
    frameEl.style.height = Math.round(frameH) + 'px';
    if (!state) {
      state = { frameW: frameW, frameH: frameH, scale: 1, dispW: 0, dispH: 0, x: 0, y: 0 };
    } else {
      state.frameW = frameW;
      state.frameH = frameH;
    }
  }

  function clearImage() {
    state = null;
    drag = null;
    if (imgEl) {
      imgEl.onload = null;
      imgEl.onerror = null;
      imgEl.removeAttribute('src');
      imgEl.style.width = '';
      imgEl.style.height = '';
      imgEl.style.transform = '';
    }
  }

  function closeModal() {
    clearImage();
    if (modalEl) modalEl.classList.remove('is-open');
    document.body.classList.remove('adm-crop-open');
  }

  function previewHost(input) {
    if (!input) return null;
    var host = input.closest('.adm-crop-field') || input.parentElement;
    return host || null;
  }

  function clearCropPreview(input) {
    var host = previewHost(input);
    if (!host) return;
    var existing = host.querySelector('.adm-crop-preview');
    if (existing) {
      var img = existing.querySelector('img');
      if (img && img.dataset.objectUrl) {
        try { URL.revokeObjectURL(img.dataset.objectUrl); } catch (e) {}
      }
      existing.remove();
    }
  }

  function showCropPreview(input, file, opts) {
    var host = previewHost(input);
    if (!host || !file) return;
    clearCropPreview(input);
    var wrap = document.createElement('div');
    wrap.className = 'adm-crop-preview' + (opts && opts.kind === 'signature' ? ' is-signature' : ' is-photo');
    var img = document.createElement('img');
    img.alt = (opts && opts.label ? opts.label + ' preview' : 'Cropped preview');
    var url = URL.createObjectURL(file);
    img.dataset.objectUrl = url;
    img.src = url;
    wrap.appendChild(img);
    var cap = document.createElement('div');
    cap.className = 'adm-crop-preview-cap';
    cap.textContent =
      'Cropped preview' +
      (opts && opts.width && opts.height ? ' (' + opts.width + '×' + opts.height + ' px)' : '');
    wrap.appendChild(cap);
    host.appendChild(wrap);
  }

  function cancelCrop() {
    if (pending && pending.input) {
      pending.input.value = '';
      clearCropPreview(pending.input);
      if (pending.errEl) {
        pending.errEl.textContent = '';
        pending.errEl.classList.add('d-none');
      }
    }
    pending = null;
    closeModal();
  }

  function applyCrop() {
    if (!pending || !state) return;
    var nat = naturalSize();
    if (!nat.w || !nat.h) return;

    // Map frame rect into natural image coordinates
    var sx = (-state.x) / state.scale;
    var sy = (-state.y) / state.scale;
    var sw = state.frameW / state.scale;
    var sh = state.frameH / state.scale;

    sx = Math.max(0, Math.min(nat.w - sw, sx));
    sy = Math.max(0, Math.min(nat.h - sh, sy));
    sw = Math.min(sw, nat.w - sx);
    sh = Math.min(sh, nat.h - sy);

    var outW = pending.width;
    var outH = pending.height;
    var canvas = document.createElement('canvas');
    canvas.width = outW;
    canvas.height = outH;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, outW, outH);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(imgEl, sx, sy, sw, sh, 0, 0, outW, outH);

    var mime = pending.mime || 'image/jpeg';
    var quality = pending.quality != null ? pending.quality : 0.9;
    var optsSnapshot = pending;

    canvas.toBlob(function (blob) {
      if (!blob) {
        cancelCrop();
        return;
      }
      if (optsSnapshot.maxOutputBytes && blob.size > optsSnapshot.maxOutputBytes) {
        if (optsSnapshot.errEl) {
          optsSnapshot.errEl.textContent =
            optsSnapshot.label +
            ' is too large after crop (' +
            (blob.size / 1024).toFixed(0) +
            ' KB). Maximum is ' +
            (optsSnapshot.maxOutputBytes / 1024) +
            ' KB.';
          optsSnapshot.errEl.classList.remove('d-none');
        }
        optsSnapshot.input.value = '';
        pending = null;
        closeModal();
        return;
      }
      var name =
        optsSnapshot.fileName ||
        (optsSnapshot.kind === 'signature' ? 'signature.jpg' : 'photo.jpg');
      var file = new File([blob], name, { type: mime, lastModified: Date.now() });
      try {
        var dt = new DataTransfer();
        dt.items.add(file);
        optsSnapshot.input.files = dt.files;
      } catch (err) {
        if (optsSnapshot.errEl) {
          optsSnapshot.errEl.textContent =
            'Could not attach cropped image. Please try another browser.';
          optsSnapshot.errEl.classList.remove('d-none');
        }
        optsSnapshot.input.value = '';
        pending = null;
        closeModal();
        return;
      }
      if (optsSnapshot.errEl) {
        optsSnapshot.errEl.textContent = '';
        optsSnapshot.errEl.classList.add('d-none');
      }
      showCropPreview(optsSnapshot.input, file, optsSnapshot);
      if (typeof optsSnapshot.onCropped === 'function') {
        optsSnapshot.onCropped(file);
      }
      pending = null;
      closeModal();
    }, mime, quality);
  }

  function openCrop(file, opts) {
    ensureModal();
    pending = opts;
    document.getElementById('admCropTitle').textContent = opts.title || 'Crop image';
    hintEl.textContent =
      'Frame is fixed. Drag the photo to position it. Use + / − (or scroll) to zoom. Output: ' +
      opts.width +
      '×' +
      opts.height +
      ' px.';

    clearImage();
    layoutFrame();
    frameEl.classList.toggle('is-wide', opts.width / opts.height > 1.5);

    var url = URL.createObjectURL(file);
    imgEl.onload = function () {
      URL.revokeObjectURL(url);
      layoutFrame();
      fitImage(true);
      modalEl.classList.add('is-open');
      document.body.classList.add('adm-crop-open');
      // Re-layout after paint in case stage size settled
      requestAnimationFrame(function () {
        layoutFrame();
        fitImage(true);
      });
    };
    imgEl.onerror = function () {
      URL.revokeObjectURL(url);
      if (opts.errEl) {
        opts.errEl.textContent = 'Could not read that image.';
        opts.errEl.classList.remove('d-none');
      }
      opts.input.value = '';
      pending = null;
      closeModal();
    };
    imgEl.src = url;
  }

  function bind(inputOrId, options) {
    var input = typeof inputOrId === 'string' ? document.getElementById(inputOrId) : inputOrId;
    if (!input || !options) return;
    var errEl = options.errId ? document.getElementById(options.errId) : options.errEl || null;
    var maxSource = options.maxSourceBytes || 10 * 1024 * 1024;
    var maxOutput = options.maxOutputBytes || options.maxBytes || 1 * 1024 * 1024;

    input.setAttribute('data-adm-crop', '1');
    if (!input.closest('.adm-crop-field') && input.parentElement) {
      input.parentElement.classList.add('adm-crop-field');
    }

    input.addEventListener('change', function () {
      if (errEl) {
        errEl.textContent = '';
        errEl.classList.add('d-none');
      }
      var f = input.files && input.files[0];
      if (!f) {
        clearCropPreview(input);
        return;
      }
      // Hide any leftover auto-preview of the original full image
      clearCropPreview(input);
      var host = previewHost(input);
      if (host) {
        host.querySelectorAll('img:not(.adm-crop-preview img)').forEach(function (el) {
          if (!el.closest('.adm-crop-preview') && el.parentElement === host) el.remove();
        });
      }
      if (!/^image\/(jpeg|png|jpg)/i.test(f.type) && !/\.(jpe?g|png)$/i.test(f.name || '')) {
        if (errEl) {
          errEl.textContent = (options.label || 'Image') + ' must be a JPG or PNG.';
          errEl.classList.remove('d-none');
        }
        input.value = '';
        return;
      }
      if (f.size > maxSource) {
        if (errEl) {
          errEl.textContent =
            (options.label || 'Image') +
            ' source is too large (' +
            (f.size / (1024 * 1024)).toFixed(1) +
            ' MB). Maximum before crop is ' +
            (maxSource / (1024 * 1024)) +
            ' MB.';
          errEl.classList.remove('d-none');
        }
        input.value = '';
        return;
      }
      openCrop(f, {
        input: input,
        errEl: errEl,
        width: options.width,
        height: options.height,
        maxOutputBytes: maxOutput,
        label: options.label || 'Image',
        title: options.title || ('Crop ' + (options.label || 'image')),
        kind: options.kind || 'photo',
        mime: options.mime || 'image/jpeg',
        quality: options.quality != null ? options.quality : 0.9,
        fileName: options.fileName,
        onCropped: options.onCropped,
      });
    });
  }

  global.AdmissionImageCrop = { bind: bind };
})(window);
