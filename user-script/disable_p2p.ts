// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     Disable P2P feature (WebRTC)
// @description disable p2p connection on all page (for firefox, go to `about:config` and set `media.peerconnection.enabled` to false instead)
// @grant    none
// @run-at   document-start
// @include	 *
// ==/UserScript==

// document-start not work in firefox
// https://github.com/greasemonkey/greasemonkey/issues/2526

declare global {
  interface Window {
    mozRTCPeerConnection?: RTCPeerConnection;
    webkitRTCPeerConnection?: RTCPeerConnection;
    DataChannel?: RTCDataChannel;
  }
}

export {};

delete window.RTCPeerConnection;
delete window.mozRTCPeerConnection;
delete window.webkitRTCPeerConnection;
delete window.RTCDataChannel;
delete window.DataChannel;
