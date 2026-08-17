import Darwin

public enum SafeStdIO {
    public static func installSignalHandling() {
        signal(SIGPIPE, SIG_IGN)
    }

    @discardableResult
    public static func writeLine(_ text: String, to fileDescriptor: Int32) -> Bool {
        var bytes = Array(text.utf8)
        bytes.append(0x0A)

        return bytes.withUnsafeBytes { buffer in
            guard let baseAddress = buffer.baseAddress else { return false }

            var offset = 0
            while offset < buffer.count {
                let written = Darwin.write(fileDescriptor,
                                           baseAddress.advanced(by: offset),
                                           buffer.count - offset)
                if written > 0 {
                    offset += written
                    continue
                }
                if written == -1 && errno == EINTR {
                    continue
                }
                return false
            }
            return true
        }
    }
}