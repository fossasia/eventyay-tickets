export const TTSParser = {
    parseFrame: function(buffer) {
        if (buffer.byteLength < 5) {
            throw new Error("Frame too short");
        }
        
        const dataView = new DataView(buffer);
        const version = dataView.getUint8(0);
        
        if (version !== 1) {
            throw new Error("Unsupported protocol version: " + version);
        }
        
        const jsonLength = dataView.getUint32(1, false); // false = big endian
        
        if (buffer.byteLength < 5 + jsonLength) {
            throw new Error("Frame truncated");
        }
        
        const jsonBytes = new Uint8Array(buffer, 5, jsonLength);
        const decoder = new TextDecoder('utf-8');
        const jsonString = decoder.decode(jsonBytes);
        
        let header;
        try {
            header = JSON.parse(jsonString);
        } catch (e) {
            throw new Error("Invalid JSON header: " + e.message);
        }
        
        const audioBytes = new Uint8Array(buffer, 5 + jsonLength);
        
        return {
            header: header,
            audioBytes: audioBytes
        };
    }
};
