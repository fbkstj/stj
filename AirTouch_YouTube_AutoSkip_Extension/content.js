// AirTouch YouTube 0秒自動跳過廣告核心腳本 (24/7 背景無感守護)
(function() {
    'use strict';
    console.log('[AirTouch Extension] 🛡️ YouTube 0秒廣告守護外掛已常駐運行！');

    function scanAndSkip() {
        // 1. 尋找所有現代與經典 YouTube 略過按鈕 (包括「略過 ▶|」、「略過廣告」等)
        const selectors = [
            '.ytp-skip-ad-button',
            '.ytp-ad-skip-button',
            '.ytp-ad-skip-button-modern',
            'button.ytp-ad-skip-button-modern',
            '.ytp-ad-skip-button-container button',
            '[id^="skip-button"] button',
            '.ytp-ad-overlay-close-button'
        ];

        for (const sel of selectors) {
            const btn = document.querySelector(sel);
            if (btn && btn.offsetParent !== null) {
                btn.click();
                console.log('[AirTouch Extension] ⚡ 0毫秒命中並點擊略過廣告按鈕！');
                return;
            }
        }

        // 2. 遇不可略過廣告或倒數期間：16 倍速光速飆過 + 自動靜音
        const adContainer = document.querySelector('.ad-showing, .ad-interrupting, .video-ads');
        const video = document.querySelector('video.html5-main-video') || document.querySelector('video');

        if (adContainer && video) {
            video.muted = true;
            video.playbackRate = 16.0;
            if (video.duration && isFinite(video.duration) && video.currentTime < video.duration - 0.5) {
                video.currentTime = video.duration - 0.1;
            }
        }
    }

    // 每 80 毫秒極速巡邏
    setInterval(scanAndSkip, 80);

    // 監聽 DOM 動態變更，零延遲秒按
    const observer = new MutationObserver(scanAndSkip);
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true
    });
})();
