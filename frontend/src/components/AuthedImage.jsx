import { useState, useEffect } from "react";
import { fetchAuthedObjectUrl } from "../services/api";

/**
 * Renders an image from an auth-protected endpoint (e.g. /api/upload/{id}).
 * Fetches the bytes with the login token, turns them into a temporary
 * in-memory object URL, and cleans it up on unmount. With openOnClick, clicking
 * opens the same object URL in a new tab (no token leaks into any URL).
 */
export default function AuthedImage({ src, alt, style, openOnClick = false }) {
  const [objUrl, setObjUrl] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let created = null;
    setObjUrl(null);
    setError(false);
    fetchAuthedObjectUrl(src)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        created = url;
        setObjUrl(url);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [src]);

  if (error) {
    return (
      <div style={{ ...style, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#999", background: "rgba(255,255,255,0.04)" }}>
        unavailable
      </div>
    );
  }

  if (!objUrl) {
    return <div style={{ ...style, background: "rgba(255,255,255,0.04)" }} />;
  }

  return (
    <img
      src={objUrl}
      alt={alt}
      style={style}
      onClick={openOnClick ? () => window.open(objUrl, "_blank", "noopener") : undefined}
    />
  );
}
