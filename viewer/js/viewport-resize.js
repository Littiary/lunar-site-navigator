// Resize only the display area; camera and package state remain owned by the view.
export function enableViewportResize(container) {
  const desktop = matchMedia("(min-width: 901px) and (hover: hover) and (pointer: fine)");
  container.classList.add("resizable-viewport");
  let drag = null;
  function resize(width, height) {
    const parent = container.parentElement, style = getComputedStyle(parent);
    const maxWidth = parent.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    container.style.width = `${Math.max(Math.min(280, maxWidth), Math.min(maxWidth, width))}px`;
    container.style.height = `${Math.max(parseFloat(getComputedStyle(container).minHeight), Math.min(1200, height))}px`;
  }
  for (const axis of ["e", "s", "se"]) {
    const handle = document.createElement("button");
    handle.type = "button";
    handle.className = `viewport-resize viewport-resize-${axis}`;
    handle.title = `Resize view ${axis === "e" ? "width" : axis === "s" ? "height" : "width and height"} (drag or arrow keys)`;
    handle.setAttribute("aria-label", handle.title);
    handle.addEventListener("pointerdown", (event) => {
      if (!desktop.matches || event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      const box = container.getBoundingClientRect();
      drag = { x: event.clientX, y: event.clientY, width: box.width, height: box.height };
      handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener("pointermove", (event) => {
      if (!drag || !desktop.matches) return;
      resize(drag.width + (axis.includes("e") ? event.clientX - drag.x : 0),
        drag.height + (axis.includes("s") ? event.clientY - drag.y : 0));
    });
    for (const event of ["pointerup", "pointercancel", "lostpointercapture"]) {
      handle.addEventListener(event, () => { drag = null; });
    }
    handle.addEventListener("keydown", (event) => {
      if (!desktop.matches || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
      event.preventDefault();
      const box = container.getBoundingClientRect(), step = event.shiftKey ? 50 : 10;
      resize(box.width + (axis.includes("e") ? ({ ArrowLeft: -step, ArrowRight: step }[event.key] || 0) : 0),
        box.height + (axis.includes("s") ? ({ ArrowUp: -step, ArrowDown: step }[event.key] || 0) : 0));
    });
    container.appendChild(handle);
  }
  desktop.addEventListener("change", () => {
    drag = null;
    if (!desktop.matches) {
      container.style.removeProperty("width");
      container.style.removeProperty("height");
    }
  });
}
