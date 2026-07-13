import { useEffect } from "react";

function enhanceScrollableRegions() {
  document.querySelectorAll<HTMLElement>(".scoped-scroll-list, .system-health-list, .mission-list").forEach((region) => {
    const scrollable = region.scrollHeight > region.clientHeight + 1 || region.scrollWidth > region.clientWidth + 1;
    if (!scrollable) {
      region.removeAttribute("aria-label");
      region.removeAttribute("role");
      region.removeAttribute("tabindex");
      return;
    }
    const panelTitle = region.closest(".panel")?.querySelector("h2")?.textContent?.trim() || "Workspace records";
    region.setAttribute("aria-label", `${panelTitle} scrollable records`);
    region.setAttribute("role", "region");
    region.setAttribute("tabindex", "0");
  });
}

export default function ScrollableRegionAccessibility() {
  useEffect(() => {
    let animationFrame = window.requestAnimationFrame(enhanceScrollableRegions);
    const scheduleEnhancement = () => {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(enhanceScrollableRegions);
    };
    const observer = new MutationObserver(scheduleEnhancement);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("resize", scheduleEnhancement);
    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", scheduleEnhancement);
    };
  }, []);
  return null;
}
