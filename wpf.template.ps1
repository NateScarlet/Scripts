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
    <Grid.RowDefinitions>
      <RowDefinition />
      <RowDefinition Height="40"/>
      <RowDefinition Height="24"/>
      <RowDefinition Height="40"/>
    </Grid.RowDefinitions>
    <Grid.ColumnDefinitions>
      <ColumnDefinition />
      <ColumnDefinition />
    </Grid.ColumnDefinitions>
    <TextBox
      x:Name="textBox1"
      TextWrapping="Wrap"
      Text="{Binding Text1, UpdateSourceTrigger=PropertyChanged}"
      Grid.ColumnSpan="2"
      AcceptsReturn="True"
    />

    <CheckBox
      IsChecked="{Binding Bool1}" Grid.Row="1"  VerticalAlignment="Center"
      Content="Bool1"
    />

    <ComboBox
      x:Name="comboBox1"
      ItemsSource="{Binding Options1}"
      SelectedValuePath="Value"
      DisplayMemberPath="Label"
      SelectedValue="{Binding SelectedOption1}"
      Grid.Row="2"
      Grid.ColumnSpan="2"
    />

    <Button x:Name="button1" Content="Button1" Grid.Row="3"/>
    <Button
      x:Name="button2"
      Content="Button2"
      Grid.Row="3"
      Grid.Column="1"
    />
  </Grid>
</Window>
'@)) )



Add-Type -Language CSharp @'
using Microsoft.Win32;
using System.Collections.ObjectModel;

namespace NateScarlet.WPFTemplate {
  public class Option {
    public string Label
    { get; set; }

    public string Value
    { get; set; }
  }

  public class Options : ObservableCollection<Option>  {
      public Options() {
        Add(new Option()
        {
          Label = "option1",
          Value = "1",
        });
        Add(new Option()
        {
          Label = "option2",
          Value = "2",
        });
        Add(new Option()
        {
          Label = "option3",
          Value = "3",
        });
      }
  }

  public class DataContext {

    private const string RegistryPath = @"Software\NateScarlet\wpf-template";

    private RegistryKey key;

    public DataContext()
    {
        this.key = Registry.CurrentUser.OpenSubKey(RegistryPath, true);
        if (this.key == null)
        {
          this.key = Registry.CurrentUser.CreateSubKey(RegistryPath);
        }

        this.Options1 = new Options();
        this.SelectedOption1 = "1";
    }
    ~DataContext()
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

    public bool Bool1
    {
        get
        {
            return (bool)key.GetValue("Bool1", 0);
        }
        set
        {
            key.SetValue("Bool1", value, RegistryValueKind.DWord);
        }
    }

    public string TempText1
    { get; set; }
    
    public string SelectedOption1
    { get; set; }

    public Options Options1
    { get; set; }
  }
    
}
'@


$data = New-Object NateScarlet.WPFTemplate.DataContext
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
$data.SelectedOption1
