# Rescue hatch: click OK/Yes/No on any Word modal (NUIDialog) that is blocking
# COM. A stuck modal makes every wordlive call hang forever (worse than exit 3).
# Usage: pwsh -File dismiss-dialogs.ps1 [-Button OK]
param([string]$Button = "OK")

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ClassNameProperty, "NUIDialog")
$dlgs = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
if ($dlgs.Count -eq 0) { "no modal dialog"; exit 0 }
foreach ($dlg in $dlgs) {
    $texts = $dlg.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Text)))
    foreach ($t in $texts) { "dialog text: " + $t.Current.Name }
    $bcond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::NameProperty, $Button)
    $btn = $dlg.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $bcond)
    if ($btn) {
        $btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
        "clicked $Button"
    }
}
