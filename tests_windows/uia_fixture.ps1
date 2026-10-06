param([string]$WindowTitle)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = $WindowTitle
$form.Width = 420
$form.Height = 280
$field = New-Object System.Windows.Forms.TextBox
$field.Name = 'Draft'
$field.AccessibleName = 'Draft'
$field.Text = 'before'
$field.SetBounds(20, 20, 300, 25)
$form.Controls.Add($field)
$password = New-Object System.Windows.Forms.TextBox
$password.Name = 'Password'
$password.AccessibleName = 'Password'
$password.UseSystemPasswordChar = $true
$password.Text = 'private-password-fixture'
$password.SetBounds(20, 55, 300, 25)
$form.Controls.Add($password)
$label = New-Object System.Windows.Forms.Label
$label.Name = 'Outcome'
$label.Text = 'Pending'
$label.SetBounds(20, 160, 200, 30)
$form.Controls.Add($label)
$button = New-Object System.Windows.Forms.Button
$button.Text = 'Apply'
$button.AccessibleName = 'Apply'
$button.SetBounds(20, 95, 100, 30)
$button.Add_Click({$label.Text = 'Applied'})
$form.Controls.Add($button)
$form.Add_Shown({$form.Activate()})
[System.Windows.Forms.Application]::Run($form)
