(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.CropperModal = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    let currentCropTargetIndex = null;
    let currentCropPageNum = 1;
    let cropSelection = { x: 0, y: 0, w: 0, h: 0 };
    let isCroppingDrag = false;
    let cropStartPos = { x: 0, y: 0 };
    let baseCropImage = null;

    const CROP_RENDER_SCALE = 3.0;
    const CROP_EXPORT_RENDER_SCALE = 6.0;
    const CROP_EXPORT_MIN_WIDTH = 2400;
    const CROP_EXPORT_MAX_DIMENSION = 7000;
    const CROP_EXPORT_MIME = 'image/png';

    let cropElements = {};
    let appState = null;
    let appElements = null;
    let callbacks = {};

    function initCropperModal(state, elements, cb = {}) {
        appState = state;
        appElements = elements;
        callbacks = cb;

        cropElements = {
            modal: document.getElementById('crop-modal'),
            pageSelect: document.getElementById('crop-page-select'),
            canvas: document.getElementById('crop-canvas'),
            closeBtn: document.getElementById('crop-modal-close'),
            cancelBtn: document.getElementById('crop-cancel-btn'),
            resetBtn: document.getElementById('crop-reset-btn'),
            saveBtn: document.getElementById('crop-save-btn'),
            statusText: document.getElementById('crop-status-text')
        };

        if (cropElements.modal && cropElements.modal.parentElement !== document.body) {
            document.body.appendChild(cropElements.modal);
        }

        cropElements.canvas?.addEventListener('mousedown', (e) => {
            const rect = cropElements.canvas.getBoundingClientRect();
            const scaleX = cropElements.canvas.width / rect.width;
            const scaleY = cropElements.canvas.height / rect.height;

            isCroppingDrag = true;
            cropStartPos = {
                x: (e.clientX - rect.left) * scaleX,
                y: (e.clientY - rect.top) * scaleY
            };
            cropSelection = { x: cropStartPos.x, y: cropStartPos.y, w: 0, h: 0 };
        });

        cropElements.canvas?.addEventListener('mousemove', (e) => {
            if (!isCroppingDrag) return;
            const rect = cropElements.canvas.getBoundingClientRect();
            const scaleX = cropElements.canvas.width / rect.width;
            const scaleY = cropElements.canvas.height / rect.height;

            const currentX = (e.clientX - rect.left) * scaleX;
            const currentY = (e.clientY - rect.top) * scaleY;

            cropSelection.x = Math.min(cropStartPos.x, currentX);
            cropSelection.y = Math.min(cropStartPos.y, currentY);
            cropSelection.w = Math.abs(currentX - cropStartPos.x);
            cropSelection.h = Math.abs(currentY - cropStartPos.y);

            redrawCropCanvas();
            if (cropElements.statusText) {
                cropElements.statusText.textContent = `אזור נבחר: ${Math.round(cropSelection.w)}x${Math.round(cropSelection.h)} px`;
            }
        });

        window.addEventListener('mouseup', () => {
            if (isCroppingDrag) {
                isCroppingDrag = false;
            }
        });

        cropElements.pageSelect?.addEventListener('change', (e) => {
            renderCropCanvasPage(e.target.value);
        });

        cropElements.resetBtn?.addEventListener('click', () => {
            cropSelection = { x: 0, y: 0, w: 0, h: 0 };
            redrawCropCanvas();
            if (cropElements.statusText) cropElements.statusText.textContent = 'סמן אזור לחיתוך בעכבר';
        });

        cropElements.closeBtn?.addEventListener('click', closeCropModal);
        cropElements.cancelBtn?.addEventListener('click', closeCropModal);

        cropElements.saveBtn?.addEventListener('click', async () => {
            if (currentCropTargetIndex === null || !appState.questions[currentCropTargetIndex]) return;
            const canvas = cropElements.canvas;
            if (!canvas || cropSelection.w < 10 || cropSelection.h < 10) {
                if (callbacks.showToast) callbacks.showToast('אנא סמן אזור תמונה רחב יותר לחיתוך.', 'error');
                return;
            }

            let croppedDataUrl = null;
            try {
                croppedDataUrl = await exportHiResCropFromPdf(currentCropPageNum, cropSelection);
            } catch (err) {
                console.warn('High-resolution crop export failed, falling back to canvas crop:', err);
            }

            if (!croppedDataUrl) {
                const offscreen = document.createElement('canvas');
                offscreen.width = cropSelection.w;
                offscreen.height = cropSelection.h;
                const ctx = offscreen.getContext('2d');
                if (!ctx) {
                    if (callbacks.showToast) callbacks.showToast('לא ניתן היה ליצור תמונת חיתוך.', 'error');
                    return;
                }
                ctx.imageSmoothingEnabled = true;
                ctx.imageSmoothingQuality = 'high';
                ctx.drawImage(
                    canvas,
                    cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h,
                    0, 0, cropSelection.w, cropSelection.h
                );
                croppedDataUrl = offscreen.toDataURL(CROP_EXPORT_MIME);
            }

            appState.questions[currentCropTargetIndex].image = croppedDataUrl;
            appState.questions[currentCropTargetIndex].imageNoCompress = true;
            if (cropElements.pageSelect) {
                appState.questions[currentCropTargetIndex].sourcePage = parseInt(cropElements.pageSelect.value, 10);
            }

            closeCropModal();
            if (callbacks.renderPreview) callbacks.renderPreview();
            if (callbacks.showToast) callbacks.showToast('תמונת השאלה עודכנה ונחתכה בהצלחה!', 'success');
        });
    }

    async function getPdfBytesForCrop() {
        if (appState?.pdfBytes && appState.pdfBytes.length > 0) {
            return new Uint8Array(appState.pdfBytes);
        }

        if (appState?.pdfArrayBuffer && appState.pdfArrayBuffer.byteLength > 0) {
            appState.pdfBytes = new Uint8Array(appState.pdfArrayBuffer.slice(0));
            return new Uint8Array(appState.pdfBytes);
        }

        const pdfInput = appElements?.pdfFile?.files?.[0];
        if (pdfInput) {
            const buffer = await pdfInput.arrayBuffer();
            appState.pdfArrayBuffer = buffer.slice(0);
            appState.pdfBytes = new Uint8Array(buffer);
            return new Uint8Array(appState.pdfBytes);
        }

        return null;
    }

    async function resolveCropTotalPages() {
        const cachedPages = appState?.pdfPagesState?.length || appState?.proofPageImages?.length || 0;
        if (cachedPages > 0) return cachedPages;

        const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
        if (!pdfjs?.getDocument) return 0;

        try {
            const bytes = await getPdfBytesForCrop();
            if (!bytes || !bytes.length) return 0;
            const pdfDoc = await pdfjs.getDocument({ data: bytes }).promise;
            return pdfDoc.numPages || 0;
        } catch (err) {
            console.warn('Could not resolve PDF page count for crop modal:', err);
            return 0;
        }
    }

    async function attachFullSourcePageImage(questionIndex, pageNum) {
        if (!appState?.questions[questionIndex]) return;

        const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
        if (!pdfjs?.getDocument) {
            if (callbacks.showToast) callbacks.showToast('ספריית PDF.js לא נטענה בדפדפן.', 'error');
            return;
        }

        try {
            const bytes = await getPdfBytesForCrop();
            if (!bytes || !bytes.length) {
                if (callbacks.showToast) callbacks.showToast('לא נמצא PDF זמין. העלה קובץ PDF ונסה שוב.', 'error');
                return;
            }

            const pdfDoc = await pdfjs.getDocument({ data: bytes }).promise;
            const safePage = Math.min(Math.max(1, Number(pageNum) || 1), pdfDoc.numPages);
            const page = await pdfDoc.getPage(safePage);

            const renderFn = callbacks.renderPageImageData || (typeof window !== 'undefined' && window.PdfService ? window.PdfService.renderPageImageData : null);
            const imageData = await renderFn(page, 2.5);
            appState.questions[questionIndex].image = `data:image/png;base64,${imageData}`;
            appState.questions[questionIndex].sourcePage = safePage;
            appState.questions[questionIndex].imageNoCompress = true;

            if (callbacks.renderPreview) callbacks.renderPreview();
            if (callbacks.showToast) callbacks.showToast(`עמוד מקור ${safePage} הוצמד לשאלה באיכות מלאה.`, 'success');
        } catch (err) {
            console.error('Failed to attach full source page image:', err);
            if (callbacks.showToast) callbacks.showToast(`שגיאה בהצמדת עמוד מקור: ${err.message || err}`, 'error');
        }
    }

    async function openCropModal(questionIndex, initialPageNum = 1) {
        currentCropTargetIndex = questionIndex;
        if (!cropElements.modal || !cropElements.canvas) return;

        cropElements.modal.style.display = 'flex';
        cropElements.modal.classList.remove('hidden');

        if (cropElements.pageSelect) {
            cropElements.pageSelect.innerHTML = '';
            const totalPages = await resolveCropTotalPages();
            if (!totalPages) {
                if (callbacks.showToast) callbacks.showToast('לא נמצא PDF זמין לחיתוך. העלה קובץ PDF בשדה "קובץ PDF" ונסה שוב.', 'error');
                closeCropModal();
                return;
            }
            for (let i = 1; i <= totalPages; i++) {
                const opt = document.createElement('option');
                opt.value = i;
                opt.textContent = `עמוד ${i}`;
                if (i === Number(initialPageNum)) opt.selected = true;
                cropElements.pageSelect.appendChild(opt);
            }
        }

        await renderCropCanvasPage(initialPageNum);
    }

    async function renderCropCanvasPage(pageNum) {
        const canvas = cropElements.canvas;
        if (!canvas) return;
        currentCropPageNum = Number(pageNum) || 1;

        cropSelection = { x: 0, y: 0, w: 0, h: 0 };
        if (cropElements.statusText) cropElements.statusText.textContent = 'סמן אזור לחיתוך בעכבר';

        const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
        if (pdfjs?.getDocument) {
            try {
                const bytes = await getPdfBytesForCrop();
                if (!bytes || !bytes.length) throw new Error('Missing PDF bytes for crop render');
                const pdfDoc = await pdfjs.getDocument({ data: bytes }).promise;
                const page = await pdfDoc.getPage(Number(pageNum));
                const viewport = page.getViewport({ scale: CROP_RENDER_SCALE });
                canvas.width = viewport.width;
                canvas.height = viewport.height;
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    ctx.imageSmoothingEnabled = true;
                    ctx.imageSmoothingQuality = 'high';
                }
                await page.render({ canvasContext: ctx, viewport }).promise;

                baseCropImage = new Image();
                baseCropImage.src = canvas.toDataURL('image/png');
                return;
            } catch (err) {
                console.warn('PDF.js render error in crop modal:', err);
            }
        }

        const pageIdx = Number(pageNum) - 1;
        const imgUrl = appState?.proofPageImages?.[pageIdx] || appState?.pdfPagesState?.[pageIdx]?.thumbnailDataUrl;
        if (imgUrl) {
            const img = new Image();
            img.onload = () => {
                canvas.width = img.naturalWidth || img.width || 800;
                canvas.height = img.naturalHeight || img.height || 1100;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                baseCropImage = img;
            };
            img.src = imgUrl;
        } else {
            const ctx = canvas.getContext('2d');
            canvas.width = 600;
            canvas.height = 400;
            ctx.fillStyle = '#1e293b';
            ctx.fillRect(0, 0, 600, 400);
            ctx.fillStyle = '#94a3b8';
            ctx.font = '16px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('לא נמצא עמוד PDF זמין לחיתוך', 300, 200);
        }
    }

    async function exportHiResCropFromPdf(pageNum, selection) {
        const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
        if (!pdfjs?.getDocument) return null;

        const bytes = await getPdfBytesForCrop();
        if (!bytes || !bytes.length) return null;

        const pdfDoc = await pdfjs.getDocument({ data: bytes }).promise;
        const safePage = Math.min(Math.max(1, Number(pageNum) || 1), pdfDoc.numPages);
        const page = await pdfDoc.getPage(safePage);

        const baseRatio = CROP_EXPORT_RENDER_SCALE / CROP_RENDER_SCALE;
        const minWidthRatio = CROP_EXPORT_MIN_WIDTH / Math.max(1, selection.w);
        let ratio = Math.max(baseRatio, minWidthRatio);
        let exportScale = CROP_RENDER_SCALE * ratio;
        let outW = Math.max(1, Math.round(selection.w * ratio));
        let outH = Math.max(1, Math.round(selection.h * ratio));

        const maxSide = Math.max(outW, outH);
        if (maxSide > CROP_EXPORT_MAX_DIMENSION) {
            const downscale = CROP_EXPORT_MAX_DIMENSION / maxSide;
            exportScale = Math.max(CROP_RENDER_SCALE, exportScale * downscale);
            ratio = exportScale / CROP_RENDER_SCALE;
            outW = Math.max(1, Math.round(selection.w * ratio));
            outH = Math.max(1, Math.round(selection.h * ratio));
        }

        const sx = Math.max(0, selection.x * ratio);
        const sy = Math.max(0, selection.y * ratio);

        const viewport = page.getViewport({ scale: exportScale });
        const fullCanvas = document.createElement('canvas');
        fullCanvas.width = Math.max(1, Math.round(viewport.width));
        fullCanvas.height = Math.max(1, Math.round(viewport.height));
        const fullCtx = fullCanvas.getContext('2d');
        if (!fullCtx) return null;
        fullCtx.imageSmoothingEnabled = true;
        fullCtx.imageSmoothingQuality = 'high';

        await page.render({ canvasContext: fullCtx, viewport }).promise;

        const offscreen = document.createElement('canvas');
        offscreen.width = outW;
        offscreen.height = outH;
        const ctx = offscreen.getContext('2d');
        if (!ctx) return null;
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        ctx.drawImage(fullCanvas, sx, sy, outW, outH, 0, 0, outW, outH);
        return offscreen.toDataURL(CROP_EXPORT_MIME);
    }

    function redrawCropCanvas() {
        const canvas = cropElements.canvas;
        if (!canvas || !baseCropImage) return;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(baseCropImage, 0, 0, canvas.width, canvas.height);

        if (cropSelection.w > 5 && cropSelection.h > 5) {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.drawImage(
                baseCropImage,
                cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h,
                cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h
            );

            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 2;
            ctx.strokeRect(cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h);
        }
    }

    function closeCropModal() {
        if (cropElements.modal) {
            cropElements.modal.style.display = 'none';
            cropElements.modal.classList.add('hidden');
        }
    }

    return {
        initCropperModal,
        openCropModal,
        closeCropModal,
        renderCropCanvasPage,
        exportHiResCropFromPdf,
        redrawCropCanvas,
        attachFullSourcePageImage,
        getPdfBytesForCrop,
        resolveCropTotalPages
    };
}));

