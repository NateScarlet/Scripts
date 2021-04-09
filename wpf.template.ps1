# https://devblogs.microsoft.com/powershell/wpf-powershell-part-1-hello-world-welcome-to-the-week-of-wpf/

$ErrorActionPreference = "Stop"

Add-Type –AssemblyName PresentationFramework
Add-Type –AssemblyName PresentationCore
Add-Type –AssemblyName WindowsBase

[System.Windows.Window]$mainWindow = [Windows.Markup.XamlReader]::Load( (New-Object System.Xml.XmlNodeReader ([xml]@'
<Window
  xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
  xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
  Title="MainWindow"
  Height="250"
  Width="300"
  Topmost="True"
>
  <Grid>
    <Grid.ColumnDefinitions>
      <ColumnDefinition />
      <ColumnDefinition />
    </Grid.ColumnDefinitions>
    <TextBox
      x:Name="textBox1"
      TextWrapping="Wrap"
      Text="TextBox"
      Margin="0,25,-1,0"
      Height="88"
      VerticalAlignment="Top"
      Grid.ColumnSpan="2"
    />
    <Button x:Name="button1" Content="Button1" Margin="0,177,0,10" />
    <Button
      x:Name="button2"
      Content="Button2"
      Grid.Column="1"
      Margin="0,177,0,10"
    />
  </Grid>
</Window>
'@)) )

$mainWindow.Content.FindName('button1').add_Click( 
    {
        Write-Host "button1 clicked"
    }
)
$mainWindow.Content.FindName('button2').add_Click( 
    {
        Write-Host "button2 clicked"
    }
)

$mainWindow.ShowDialog()
$mainWindow.Content.FindName('textBox1').Text
