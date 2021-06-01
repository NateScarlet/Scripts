# https://devblogs.microsoft.com/powershell/wpf-powershell-part-1-hello-world-welcome-to-the-week-of-wpf/
# https://social.technet.microsoft.com/wiki/contents/articles/7804.powershell-creating-custom-objects.aspx

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
      Text="{Binding Text1, UpdateSourceTrigger=PropertyChanged}"
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



Add-Type -Language CSharp @'
using Microsoft.Win32;

public class AppDataContext {

  private const string RegistryPath = @"Software\NateScarlet\wpf-template";

  private RegistryKey key;

  public AppDataContext()
  {
      this.key = Registry.CurrentUser.OpenSubKey(RegistryPath, true);
      if (this.key == null)
      {
          this.key = Registry.CurrentUser.CreateSubKey(RegistryPath);
      }
  }
  ~AppDataContext()
  {
    key.Dispose();
  }

  public string Text1
  {
      get
      {
          return (string)key.GetValue("Text1", "Text1 default");
      }
      set
      {
          key.SetValue("Text1", value);
      }
  }

  public string[] MultiText1
  {
      get
      {
          return (string[])key.GetValue("MultiText1", new string[]{ "text1", "text2" });
      }
      set
      {
          key.SetValue("MultiText1", value, RegistryValueKind.MultiString);
      }
  }

  public string TempText1
  { get; set; }
}
'@


$data = New-Object AppDataContext
$mainWindow.DataContext = $data
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

[void]$mainWindow.ShowDialog()
$data.Text1
