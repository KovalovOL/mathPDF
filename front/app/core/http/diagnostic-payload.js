/** Bounded diagnostic snapshots; binary responses are never consumed. */
export class DiagnosticPayload {
  static request(options) {
    if (options.body instanceof FormData)
      return {
        files: [...options.body].map(([field, file]) =>
          typeof file === "string"
            ? {
                field,
                value: file,
              }
            : {
                field,
                name: file.name,
                size: file.size,
                type: file.type,
              },
        ),
      };
    if (typeof options.body !== "string") return null;
    try {
      return JSON.parse(options.body);
    } catch {
      return {
        _unreadable: true,
      };
    }
  }
  static async response(response) {
    const mime = response.headers.get("content-type") || "";
    if (!mime.includes("json") && response.status < 400) return null;
    try {
      const text = await this.#read(response.clone());
      if (text === null)
        return {
          _truncated: true,
          reason: "response size limit",
        };
      if (!text) return null;
      try {
        return JSON.parse(text);
      } catch {
        return {
          text: text.slice(0, 5000),
          _unreadable: true,
        };
      }
    } catch {
      return {
        _unreadable: true,
      };
    }
  }
  static async #read(response) {
    const reader = response.body.getReader(),
      decoder = new TextDecoder();
    let bytes = 0,
      text = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) return text;
      bytes += value.length;
      if (bytes > 1500000) {
        await reader.cancel();
        return null;
      }
      text += decoder.decode(value, {
        stream: true,
      });
    }
  }
}
