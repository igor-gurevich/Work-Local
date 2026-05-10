"""GUI-assisted schematic review tool.

The reviewer asks for a schematic file, focus areas, and supporting reference
materials, then produces a structured engineering review using deterministic
checks that work on text-based schematic, netlist, BOM, and design-export files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext
except ModuleNotFoundError:  # pragma: no cover - depends on host Python build
    tk = None
    filedialog = None
    messagebox = None
    scrolledtext = None


TEXT_EXTENSIONS = {
    ".asc",
    ".csv",
    ".dat",
    ".dsn",
    ".json",
    ".kicad_sch",
    ".net",
    ".sch",
    ".txt",
    ".xml",
}


@dataclass(frozen=True)
class ReviewFinding:
    """A single schematic-review finding."""

    severity: str
    category: str
    message: str
    recommendation: str


@dataclass(frozen=True)
class ReviewResult:
    """Review output rendered by the GUI."""

    schematic_path: Path
    focus_areas: tuple[str, ...]
    reference_paths: tuple[Path, ...]
    findings: tuple[ReviewFinding, ...]
    notes: tuple[str, ...]

    def to_text(self) -> str:
        lines = [
            "Schematics Review",
            f"Schematic: {self.schematic_path}",
            "Focus areas: " + (", ".join(self.focus_areas) if self.focus_areas else "general review"),
            "Reference materials: "
            + (", ".join(str(path) for path in self.reference_paths) if self.reference_paths else "none supplied"),
            "",
            "Summary:",
            f"- Findings: {len(self.findings)}",
            f"- Notes: {len(self.notes)}",
            "",
        ]

        if self.findings:
            lines.append("Findings:")
            for index, finding in enumerate(self.findings, start=1):
                lines.extend(
                    [
                        f"{index}. [{finding.severity}] {finding.category}",
                        f"   Issue: {finding.message}",
                        f"   Recommendation: {finding.recommendation}",
                    ]
                )
        else:
            lines.extend(
                [
                    "Findings:",
                    "No obvious schematic issues were detected by the automated heuristics.",
                ]
            )

        if self.notes:
            lines.extend(["", "Review notes:"])
            lines.extend(f"- {note}" for note in self.notes)

        lines.extend(
            [
                "",
                "Limitations:",
                "- This review is heuristic and does not replace a full CAD-native design review.",
                "- For high-speed designs, verify topology, stack-up, impedance, timing, and constraints in the ECAD tool.",
            ]
        )
        return "\n".join(lines)


class SchematicsReviewer:
    """Deterministic schematic-review engine for local files."""

    def review(
        self,
        schematic_file: str | Path,
        focus_areas: str | list[str] | tuple[str, ...] = "",
        reference_materials: list[str | Path] | tuple[str | Path, ...] = (),
    ) -> ReviewResult:
        schematic_path = Path(schematic_file).expanduser()
        references = tuple(Path(path).expanduser() for path in reference_materials if str(path).strip())
        focus = self._normalize_focus(focus_areas)
        findings: list[ReviewFinding] = []
        notes: list[str] = []

        if not schematic_path.exists():
            findings.append(
                ReviewFinding(
                    "Critical",
                    "Input",
                    "The selected schematic file does not exist.",
                    "Provide the correct schematic, netlist, PDF text export, or CAD text-export path.",
                )
            )
            return ReviewResult(schematic_path, focus, references, tuple(findings), tuple(notes))

        missing_references = [path for path in references if not path.exists()]
        for path in missing_references:
            findings.append(
                ReviewFinding(
                    "Warning",
                    "Reference material",
                    f"Reference material was not found: {path}",
                    "Provide local datasheets, application notes, design guides, stack-up, and constraints used by the design.",
                )
            )

        text = self._read_schematic_text(schematic_path, notes)
        if not text.strip():
            findings.append(
                ReviewFinding(
                    "Warning",
                    "Input",
                    "No searchable text was available from the schematic file.",
                    "Export the schematic to a text netlist, PDF text, KiCad schematic, CSV connectivity report, or BOM for deeper analysis.",
                )
            )
            return ReviewResult(schematic_path, focus, references, tuple(findings), tuple(notes))

        findings.extend(self._review_connectivity(text))
        findings.extend(self._review_power_delivery(text))
        findings.extend(self._review_focus_specific(text, focus))
        findings.extend(self._review_references(references, missing_references))

        if not focus:
            notes.append("No focus areas were specified; performed general connectivity, power, and high-speed keyword checks.")
        if not references:
            notes.append("No datasheets or reference materials were supplied; component-level compliance could not be verified.")

        return ReviewResult(schematic_path, focus, references, tuple(findings), tuple(notes))

    def _read_schematic_text(self, schematic_path: Path, notes: list[str]) -> str:
        suffix = schematic_path.suffix.lower()
        if suffix not in TEXT_EXTENSIONS:
            notes.append(
                f"'{suffix or 'no extension'}' is not a known text schematic format; attempting best-effort text extraction."
            )

        try:
            content = schematic_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            notes.append(f"Could not read schematic file: {exc}")
            return ""

        if "\ufffd" in content[:500]:
            notes.append("The file appears to contain binary or non-UTF-8 content; text analysis may be incomplete.")
        return content

    def _normalize_focus(self, focus_areas: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
        if isinstance(focus_areas, str):
            parts = re.split(r"[,;\n]+", focus_areas)
        else:
            parts = list(focus_areas)
        return tuple(part.strip().lower() for part in parts if part and part.strip())

    def _review_connectivity(self, text: str) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        lower_text = text.lower()
        if re.search(r"\b(no\s*connect|unconnected|floating|not\s+connected)\b", lower_text):
            findings.append(
                ReviewFinding(
                    "High",
                    "Connectivity",
                    "The schematic text contains unconnected or floating-net markers.",
                    "Confirm every intentional NC pin is marked according to the component datasheet and resolve accidental opens.",
                )
            )

        diff_nets = self._extract_differential_nets(text)
        for base_name, polarities in diff_nets.items():
            if polarities != {"p", "n"}:
                missing = "N" if "n" not in polarities else "P"
                findings.append(
                    ReviewFinding(
                        "High",
                        "Differential pairs",
                        f"Differential pair '{base_name}' is missing the {missing} polarity in the searchable connectivity.",
                        "Verify the pair naming, polarity, and end-to-end connectivity against the connector/device pinout.",
                    )
                )

        if re.search(r"\b(txp|txn|rxp|rxn|pcie|usb|ethernet|serdes)\b", lower_text) and not diff_nets:
            findings.append(
                ReviewFinding(
                    "Medium",
                    "Differential pairs",
                    "High-speed differential keywords were found, but pair names could not be matched automatically.",
                    "Confirm all P/N nets are consistently named, length matched, polarity correct, and constrained in layout.",
                )
            )

        return findings

    def _review_power_delivery(self, text: str) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        lower_text = text.lower()
        power_keywords = re.findall(r"\b(vdd|vcc|vtt|vref|avdd|dvdd|pvdd|vin|vout|gnd)\b", lower_text)
        capacitor_keywords = re.findall(r"\b(c\d+|capacitor|decoupling|bulk|uf|nf|pf)\b", lower_text)

        if power_keywords and not capacitor_keywords:
            findings.append(
                ReviewFinding(
                    "High",
                    "Power delivery",
                    "Power nets were detected, but no decoupling capacitor evidence was found in the text export.",
                    "Check that each IC rail has local high-frequency decoupling, appropriate bulk capacitance, and a validated PDN target impedance.",
                )
            )

        if re.search(r"\bvref\b|\bvtt\b", lower_text) and "tolerance" not in lower_text:
            findings.append(
                ReviewFinding(
                    "Medium",
                    "Power delivery",
                    "Reference or termination rails are present without visible tolerance requirements.",
                    "Document voltage tolerance, noise limits, sequencing, and load current for VREF/VTT-style rails.",
                )
            )

        return findings

    def _review_focus_specific(self, text: str, focus_areas: tuple[str, ...]) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        review_text = " ".join((text.lower(), *focus_areas))

        if "pcie" in review_text:
            findings.extend(self._pcie_findings(text.lower()))
        if "ddr" in review_text:
            findings.extend(self._ddr_findings(text.lower()))
        if "ethernet" in review_text or "eth" in focus_areas:
            findings.extend(self._ethernet_findings(text.lower()))
        if "power" in review_text or "pdn" in review_text:
            findings.append(
                ReviewFinding(
                    "Info",
                    "Power delivery",
                    "Power-delivery review requested.",
                    "Cross-check regulator stability, load transients, sequencing, sense routing, current limits, thermals, and derating.",
                )
            )
        if "signal integrity" in review_text or "si" in focus_areas:
            findings.append(
                ReviewFinding(
                    "Info",
                    "Signal integrity",
                    "Signal-integrity review requested.",
                    "Verify stack-up, impedance tables, return-path continuity, reference-plane changes, via stubs, and crosstalk spacing.",
                )
            )

        return findings

    def _pcie_findings(self, lower_text: str) -> list[ReviewFinding]:
        findings = [
            ReviewFinding(
                "Info",
                "PCIe",
                "PCIe review requested or PCIe nets detected.",
                "Verify lane polarity, PERST#, REFCLK architecture, WAKE#, SMBus sideband requirements, equalization assumptions, and connector pinout.",
            )
        ]
        if "100nf" not in lower_text and "0.1uf" not in lower_text and "ac coupling" not in lower_text:
            findings.append(
                ReviewFinding(
                    "Medium",
                    "PCIe",
                    "No visible PCIe AC-coupling capacitor evidence was found.",
                    "Confirm TX AC-coupling capacitor placement, value, voltage rating, and side-of-link ownership per the PCIe specification and endpoint guide.",
                )
            )
        if "refclk" not in lower_text and "reference clock" not in lower_text:
            findings.append(
                ReviewFinding(
                    "Medium",
                    "PCIe",
                    "No visible PCIe reference-clock signal was found.",
                    "Confirm REFCLK routing, common-clock/SRIS/SRNS mode, termination, jitter budget, and clock-request behavior.",
                )
            )
        return findings

    def _ddr_findings(self, lower_text: str) -> list[ReviewFinding]:
        findings = [
            ReviewFinding(
                "Info",
                "DDR",
                "DDR review requested or DDR nets detected.",
                "Verify fly-by topology, byte-lane grouping, address/command/control termination, ZQ, reset, clocks, and training requirements.",
            )
        ]
        for rail in ("vddq", "vpp", "vref"):
            if rail not in lower_text:
                findings.append(
                    ReviewFinding(
                        "Medium",
                        "DDR",
                        f"No visible {rail.upper()} rail was found.",
                        f"Confirm {rail.upper()} implementation, decoupling, tolerance, sequencing, and device-specific requirements.",
                    )
                )
        return findings

    def _ethernet_findings(self, lower_text: str) -> list[ReviewFinding]:
        findings = [
            ReviewFinding(
                "Info",
                "Ethernet",
                "Ethernet review requested or Ethernet-related text detected.",
                "Verify PHY strap pins, magnetics, Bob Smith termination, center taps, ESD protection, isolation, and LED polarity.",
            )
        ]
        if "magnetics" not in lower_text and "transformer" not in lower_text:
            findings.append(
                ReviewFinding(
                    "Medium",
                    "Ethernet",
                    "No visible Ethernet magnetics or transformer evidence was found.",
                    "Confirm the PHY-to-magnetics-to-connector topology, return loss network, isolation ratings, and common-mode choke selection.",
                )
            )
        return findings

    def _extract_differential_nets(self, text: str) -> dict[str, set[str]]:
        net_pattern = re.compile(r"\b([A-Za-z][A-Za-z0-9_\-/]*?)(?:[_\-]?(P|N)|([PN]))(?:\[\d+\])?\b")
        pairs: dict[str, set[str]] = {}
        for match in net_pattern.finditer(text):
            base = match.group(1).rstrip("_-/")
            polarity = (match.group(2) or match.group(3) or "").lower()
            if len(base) < 2 or polarity not in {"p", "n"}:
                continue
            if any(token in base.lower() for token in ("tx", "rx", "clk", "dq", "dqs", "pcie", "usb", "eth")):
                pairs.setdefault(base.upper(), set()).add(polarity)
        return pairs

    def _review_references(self, references: tuple[Path, ...], missing_references: list[Path]) -> list[ReviewFinding]:
        if references and len(references) == len(missing_references):
            return [
                ReviewFinding(
                    "Warning",
                    "Reference material",
                    "None of the supplied reference materials could be found.",
                    "Attach the relevant datasheets, application notes, design guides, board constraints, and stack-up files for source-backed review.",
                )
            ]
        return []


class SchematicsReviewerApp:
    """Tkinter GUI for the schematic reviewer."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Schematics Reviewer")
        self.reviewer = SchematicsReviewer()
        self.reference_paths: list[Path] = []

        self.schematic_var = tk.StringVar()
        self.focus_var = tk.StringVar(value="PCIe, DDR, Ethernet, power delivery, signal integrity")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Schematic file").grid(row=0, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.schematic_var, width=80).grid(row=1, column=0, sticky="ew")
        tk.Button(frame, text="Browse...", command=self._browse_schematic).grid(row=1, column=1, padx=(8, 0))

        tk.Label(frame, text="Focus areas").grid(row=2, column=0, sticky="w", pady=(10, 0))
        tk.Entry(frame, textvariable=self.focus_var, width=80).grid(row=3, column=0, columnspan=2, sticky="ew")

        tk.Label(frame, text="Datasheets / reference materials").grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.references_box = tk.Listbox(frame, height=4)
        self.references_box.grid(row=5, column=0, sticky="ew")
        ref_buttons = tk.Frame(frame)
        ref_buttons.grid(row=5, column=1, sticky="n", padx=(8, 0))
        tk.Button(ref_buttons, text="Add...", command=self._add_references).pack(fill=tk.X)
        tk.Button(ref_buttons, text="Clear", command=self._clear_references).pack(fill=tk.X, pady=(4, 0))

        tk.Button(frame, text="Run review", command=self._run_review).grid(row=6, column=0, sticky="w", pady=(10, 0))
        tk.Button(frame, text="Save feedback...", command=self._save_feedback).grid(row=6, column=1, sticky="e", pady=(10, 0))

        self.output = scrolledtext.ScrolledText(frame, width=100, height=28, wrap=tk.WORD)
        self.output.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(10, 0))

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(7, weight=1)

    def _browse_schematic(self) -> None:
        filename = filedialog.askopenfilename(title="Select schematic or netlist file")
        if filename:
            self.schematic_var.set(filename)

    def _add_references(self) -> None:
        filenames = filedialog.askopenfilenames(title="Select datasheets or reference materials")
        for filename in filenames:
            path = Path(filename)
            if path not in self.reference_paths:
                self.reference_paths.append(path)
                self.references_box.insert(tk.END, str(path))

    def _clear_references(self) -> None:
        self.reference_paths.clear()
        self.references_box.delete(0, tk.END)

    def _run_review(self) -> None:
        schematic_file = self.schematic_var.get().strip()
        if not schematic_file:
            messagebox.showerror("Missing schematic", "Select where to find the schematic file before running the review.")
            return

        result = self.reviewer.review(schematic_file, self.focus_var.get(), self.reference_paths)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, result.to_text())

    def _save_feedback(self) -> None:
        feedback = self.output.get("1.0", tk.END).strip()
        if not feedback:
            messagebox.showinfo("No feedback", "Run a review before saving feedback.")
            return

        filename = filedialog.asksaveasfilename(
            title="Save schematic review",
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
        if filename:
            Path(filename).write_text(feedback, encoding="utf-8")


def main() -> None:
    if tk is None:
        raise SystemExit("Tkinter is required to launch the GUI. Install the Python Tkinter package for your OS.")

    root = tk.Tk()
    SchematicsReviewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
