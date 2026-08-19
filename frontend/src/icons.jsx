const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.9,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function IconBrand(props) {
  return (
    <svg {...base} {...props}>
      <path d="M4 4.5h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9.5l-4.8 3.8V17.5H4a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1z" />
      <path d="M7.5 9.5h9" />
      <path d="M7.5 13h5.5" />
    </svg>
  );
}

export function IconSpark(props) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3l2.4 5.6L20 11l-5.6 2.4L12 19l-2.4-5.6L4 11l5.6-2.4z" />
    </svg>
  );
}

export function IconUpload(props) {
  return (
    <svg {...base} strokeWidth={2} {...props}>
      <path d="M12 15.5V4" />
      <path d="M7.5 8.5 12 4l4.5 4.5" />
      <path d="M4.5 15.5V18a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-2.5" />
    </svg>
  );
}

export function IconFile(props) {
  return (
    <svg {...base} strokeWidth={1.8} {...props}>
      <path d="M7 3.5h6.5L18 8v11.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z" />
      <path d="M13.5 3.5V8H18" />
      <path d="M9 13h6" />
      <path d="M9 16.5h6" />
    </svg>
  );
}

export function IconTrash(props) {
  return (
    <svg {...base} strokeWidth={1.8} {...props}>
      <path d="M5 7h14" />
      <path d="M9.5 7V4.6a.6.6 0 0 1 .6-.6h3.8a.6.6 0 0 1 .6.6V7" />
      <path d="M7 7l.9 12.1a1.5 1.5 0 0 0 1.5 1.4h5.2a1.5 1.5 0 0 0 1.5-1.4L17 7" />
    </svg>
  );
}

export function IconSend(props) {
  return (
    <svg {...base} strokeWidth={2} {...props}>
      <path d="M21 3 10.5 13.5" />
      <path d="M21 3 14.5 21l-4-7.5L3 9.5z" />
    </svg>
  );
}

export function IconClose(props) {
  return (
    <svg {...base} strokeWidth={2} {...props}>
      <path d="M6 6l12 12" />
      <path d="M18 6 6 18" />
    </svg>
  );
}

export function IconRefresh(props) {
  return (
    <svg {...base} {...props}>
      <path d="M20 11a8 8 0 1 0-2.5 5.8" />
      <path d="M20 5v6h-6" />
    </svg>
  );
}
