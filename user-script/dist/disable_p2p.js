// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     Disable P2P feature (WebRTC)
// @description disable p2p connection on all page (for firefox, go to `about:config` and set `media.peerconnection.enabled` to false instead)
// @grant    none
// @run-at   document-start
// @include	 *
// @version   2021.12.09+2bcfbdc1
// ==/UserScript==

(() => {
  // disable_p2p.ts
  delete window.RTCPeerConnection;
  delete window.mozRTCPeerConnection;
  delete window.webkitRTCPeerConnection;
  delete window.RTCDataChannel;
  delete window.DataChannel;
})();
