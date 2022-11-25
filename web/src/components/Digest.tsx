// Display a digest string.

import * as React from "react";

export interface DigestProps {
  digest: string;
  chars?: number;
}

// Displays a digest string.
//
// Uses a span to display the first 7 characters of the digest string, with a
// `title` attribute which causes the entire digest to appear on hover.
export const Digest: React.FC<DigestProps> = ({ digest, chars = 7 }) => {
  // Todo: it would be nice to:
  // 1. make this clickable to display a context menu item
  // 2. have a clean way for the user to copy the full digest value to the
  //    clipboard.
  return <span title={digest}>{digest.slice(0, chars)}</span>;
};
