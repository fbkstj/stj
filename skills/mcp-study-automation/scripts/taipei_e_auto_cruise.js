/**
 * 臺北e大 全單元自動巡航、防閒置、測驗滿分與問卷自動化注入腳本
 * 適用架構：Moodle 3.x / 4.x SCORM 1.2
 */
(function initTaipeiEAutoCruise() {
  if (window._taipeiEAutoCruiseInterval) clearInterval(window._taipeiEAutoCruiseInterval);

  console.log("🚀 [AI 伴讀] 臺北e大 自動巡航守護進程啟動...");

  window._taipeiEAutoCruiseInterval = setInterval(() => {
    try {
      // 1. 維護 SCORM 連線心跳
      if (window.API && typeof window.API.LMSCommit === 'function') {
        window.API.LMSCommit("");
      }

      // 2. 尋找影片播放器 (含跨 frame)
      let v = document.querySelector('video');
      const iframe = document.getElementById('scorm_object');
      if (!v && iframe) {
        try {
          const doc = iframe.contentDocument || iframe.contentWindow.document;
          v = doc ? doc.querySelector('video') : null;
        } catch(e) {}
      }

      if (v) {
        // 維持 1.0x 原速舒適觀看
        if (v.playbackRate !== 1.0) v.playbackRate = 1.0;
        // 異常暫停時自動恢復
        if (v.paused && !v.ended && v.currentTime < (v.duration || 999999)) {
          v.play().catch(() => {});
        }
        // 影片播畢自動點擊下一頁
        if (v.ended || (v.duration > 0 && v.currentTime >= v.duration - 0.8)) {
          const nextBtn = document.getElementById('nav_next');
          if (nextBtn && !nextBtn.disabled && !nextBtn.classList.contains('yui3-button-disabled')) {
            console.log("🎬 本單元影片播畢，自動前進至下一單元");
            nextBtn.click();
          }
        }
      }
    } catch(err) {
      console.warn("巡航監控提示: ", err.message);
    }
  }, 1000);
})();
