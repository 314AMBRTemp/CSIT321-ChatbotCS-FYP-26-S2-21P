$(document).ready(function() {
	// Banner animation
	var myFunction = function() {
		console.log("done");
	};

	var fullLock = $('#full-lock-svg'),
		lock = $('#lock'),
		lock_body = $('#lock-body'),
		keyhole = $('#keyhole'),
		bottom = $('#bottom'),
		up = $('#up'),
		upPaths = $("#up [id^='up-']"),
		bottomPaths = $("#bottom [id^='bottom-']"),
		key = $("#key"),
		bannerHeadingH2 = $(".banner_heading h2"),
		bannerHeadingH3 = $(".banner_heading h3");

	tlBanner = new TimelineMax({paused: false, repeat: -1, onComplete: myFunction});

	tlBanner
		.set(fullLock, {display: 'block'})
		.fromTo(lock, 1, {
			x: -150,
			autoAlpha: 0,
			ease: Power3.easeOut
		}, {
			x: 0,
			autoAlpha: 1
		})
		.fromTo(up, 1, {
			y: -150,
			autoAlpha: 0,
			ease: Power3.easeOut
		}, {
			y: 0,
			autoAlpha: 1
		}, '-=1')
		.fromTo(bottom, 1, {
			y: 150,
			autoAlpha: 0,
			ease: Power3.easeOut
		}, {
			y: 0,
			autoAlpha: 1
		}, '-=1')
		.to(upPaths, 1, {
			fill: "rgba(255, 255, 255, 1)"
		}, '-=1')
		.to(bottomPaths, 1, {
			fill: "rgba(255, 255, 255, 1)"
		}, '-=1')
		.to(bottomPaths, .7, {
			fill: "rgba(255, 255, 255, 1)"
		}, '.5')
		.to(fullLock, 1, {
			x: 150,
			autoAlpha: 0
		}, '2')
		.fromTo(bannerHeadingH2, 1, {
			y: 150,
			autoAlpha: 0,
			ease: Power3.easeOut
		}, {
			y: 0,
			autoAlpha: 1
		}, '2.5')
		.fromTo(bannerHeadingH3, 1, {
			y: -150,
			autoAlpha: 0,
			ease: Power3.easeOut
		}, {
			y: 0,
			autoAlpha: 1
		}, '2.5')
		.to(bannerHeadingH2, 2, {
			fill: "rgba(0, 0, 0, 1)"
		}, '3.5');
});
