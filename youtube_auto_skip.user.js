// ==UserScript==
// @name         YouTube 0秒極速自動略過廣告 (AirTouch Ultra-Fast Auto Skip)
// @namespace    https://fbkstj.github.io/www/
// @version      2.0
// @description  全自動 0 秒點擊「略過廣告」按鈕，遇不可略過廣告自動 16 倍速飆過並靜音，還你純淨無干擾觀影體驗！
// @author       簡老師 (Teacher Chien) - AI 視覺與邊緣運算專題
// @match        https://www.youtube.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    console.log('[AirTouch 廣告跳過神器] 已常駐啟動！');

    function checkAndSkip() {
        // 1. 尋找所有現代與舊版 YouTube 略過按鈕
        const skipSelectors = [
            '.ytp-skip-ad-button',
            '.ytp-ad-skip-button',
            '.ytp-ad-skip-button-modern',
            'button.ytp-ad-skip-button-modern',
            '.ytp-ad-skip-button-container button',
            '[id^="skip-button"] button',
            '.ytp-ad-overlay-close-button'
        ];

        for (const selector of skipSelectors) {
            const btn = document.querySelector(selector);
            if (btn && btn.offsetParent !== null) {
                btn.click();
                console.log('[AirTouch] ⚡ 成功點擊略過廣告按鈕！');
                return;
            }
        }

        // 2. 處理正在播廣告中的影片 (加速 + 靜音策略)
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

    // 每 100 毫秒高頻極速巡邏
    setInterval(checkAndSkip, 100);

    // 監聽 DOM 動態變更 (0 毫秒響應)
    const observer = new MutationObserver(checkAndSkip);
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true
    });
})();
