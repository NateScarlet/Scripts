# https://devblogs.microsoft.com/powershell/wpf-powershell-part-1-hello-world-welcome-to-the-week-of-wpf/
# https://social.technet.microsoft.com/wiki/contents/articles/7804.powershell-creating-custom-objects.aspx

$ErrorActionPreference = "Stop"

Add-Type –AssemblyName PresentationFramework

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
      <RowDefinition Height="40"/>
      <RowDefinition />
      <RowDefinition Height="40"/>
      <RowDefinition Height="24"/>
      <RowDefinition Height="40"/>
    </Grid.RowDefinitions>
    <Grid.ColumnDefinitions>
      <ColumnDefinition />
      <ColumnDefinition />
    </Grid.ColumnDefinitions>
    <Grid Grid.ColumnSpan="2" Margin="8">
      <Grid.ColumnDefinitions>
        <ColumnDefinition Width="40"/>
        <ColumnDefinition />
        <ColumnDefinition Width="60"/>
      </Grid.ColumnDefinitions>
      
      <Label Content="Dir1" />
      <TextBox x:Name="dirInput1" Grid.Column="1" Text="{Binding Dir1}" MaxLines="1"/>
      <Button x:Name="chooseDir1Button" Grid.Column="2">choose...</Button>
    </Grid>

    <TextBox
      x:Name="textBox1"
      TextWrapping="Wrap"
      Text="{Binding Text1, UpdateSourceTrigger=PropertyChanged}"
      Grid.Row="1"
      Grid.ColumnSpan="2"
      AcceptsReturn="True"
      />
      
    <CheckBox
      IsChecked="{Binding Bool1}"
      Grid.Row="2"
      VerticalAlignment="Center"
    >Bool1</CheckBox>

    <ComboBox
      x:Name="comboBox1"
      ItemsSource="{Binding Options1}"
      SelectedValuePath="Value"
      DisplayMemberPath="Label"
      SelectedValue="{Binding SelectedOption1}"
      Grid.Row="3"
      Grid.ColumnSpan="2"
    />

    <Button
      x:Name="button1"
      Content="Button1"
      Grid.Row="4"
    />
    <Button
      x:Name="button2"
      Content="Button2"
      Grid.Row="4"
      Grid.Column="1"
    />
  </Grid>
</Window>
'@)) )



Add-Type -Language CSharp @'
using Microsoft.Win32;
using System.Collections.ObjectModel;
using System.ComponentModel;

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

  public class DataContext: INotifyPropertyChanged {
    public event PropertyChangedEventHandler PropertyChanged;
    protected virtual void OnPropertyChanged(string propertyName)
    {
        PropertyChangedEventHandler handler = PropertyChanged;
        if (handler != null) handler(this, new PropertyChangedEventArgs(propertyName));
    }
  
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
            OnPropertyChanged("Text1");
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
            OnPropertyChanged("MultiText1");
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
            OnPropertyChanged("Bool1");
        }
    }

    public string TempText1
    { get; set; }

    public string SelectedOption1
    { get; set; }
    
    public Options Options1
    { get; set; }

    private string dir1 = "C:\\";
    public string Dir1
    {
      get { return dir1; }
      set { 
        dir1 = value;
        OnPropertyChanged("Dir1");
      }
    }
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
$mainWindow.Content.FindName('chooseDir1Button').add_Click( 
  {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog -Property @{
      SelectedPath = $data.Dir1
    }
    if ($dialog.ShowDialog() -eq "OK") {
      $data.Dir1 = $dialog.SelectedPath
    }
  }
)




[void]$mainWindow.ShowDialog()
$data.Text1
$data.SelectedOption1
