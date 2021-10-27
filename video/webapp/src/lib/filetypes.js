export function getIconByFileEnding (url) {
	url = url?.toLowerCase()
	if (/\.pdf$/.test(url)) return 'file-pdf-outline'
	if (/\.xlsx?$/.test(url)) return 'file-excel-outline'
	if (/\.docx?$/.test(url)) return 'file-word-outline'
	if (/\.pptx?$/.test(url)) return 'file-powerpoint-outline'
	if (/\.(mp3|ogg|wav|flac)$/.test(url)) return 'file-music-outline'
	if (/\.(jpe?g|png|tiff)$/.test(url)) return 'file-image-outline'
	if (/(\.(mp4|mov|webm|avi)$)|\/\/(youtube\.com|youtu\.be|vimeo\.com)\//.test(url)) return 'file-video-outline'
	return 'file-download-outline'
}
