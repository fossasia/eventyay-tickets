import Color from 'color'

export const definition = {
	label: 'Initials',
	colorPalette: {
		size: 14,
		defaults: [
			'#ffcdd2',
			'#f8bbd0',
			'#e1bee7',
			'#d1c4e9',
			'#c5cae9',
			'#b2dfdb',
			'#A0F2B7',
			'#f0f4c3',
			'#fff9c4',
			'#ffecb3',
			'#ffe0b2',
			'#ffccbc',
			'#d7ccc8',
			'#cfd8dc',
		],
	},
}

export function renderSvg (random, userProfile, config) {
	const initials = userProfile.display_name
		.split(' ')
		.map((n) => n[0])
		.join('')
		.slice(0, 2)
		.toUpperCase()

	const bgColor = config.colorPalette[random.integer(0, config.colorPalette.length - 1)]

	const primaryColor = Color(bgColor)
	const secondColor = Color(bgColor)
		.rotate(-28)
		.saturationl(primaryColor.saturationl() - 15)
		.lightness(primaryColor.lightness() - 32)
		.hsl().string()
	const textColor = Color(bgColor)
		.saturationl(primaryColor.saturationl() - 10)
		.lightness(95)
		.hsl().string()
	const size = 48
	const fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif"
	const fontSize = 0.5
	const fontWeight = 500

	return `
	<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}">
		<defs>
			<radialGradient id="gradient" cx="0" cy="0" r="1" gradientTransform="scale(1.5)">
				<stop stop-color="${bgColor}" />
				<stop offset="1" stop-color="${secondColor}" />
			</radialGradient>
		</defs>	
		<circle fill="url(#gradient)" cx="${size / 2}" cy="${size / 2}" r="${
	size / 2
}"/>
		<text x="50%" y="50%" style="color: ${textColor};line-height: 1;font-family: ${fontFamily};" alignment-baseline="middle" text-anchor="middle" font-size="${Math.round(
	size * fontSize
)}" font-weight="${fontWeight}" dy=".1em" dominant-baseline="middle" fill="${textColor}">${initials}</text>
	</svg>
	`
}
