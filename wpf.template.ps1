# https://devblogs.microsoft.com/powershell/wpf-powershell-part-1-hello-world-welcome-to-the-week-of-wpf/

$ErrorActionPreference = "Stop"

Add-Type –assemblyName PresentationFramework
Add-Type –assemblyName PresentationCore
Add-Type –assemblyName WindowsBase

[xml]$xaml = @'
<Window 
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="MainWindow" Height="180.769" Width="294.617" MinHeight="250" MaxHeight="250">
    <Grid>
        <Grid.ColumnDefinitions>
            <ColumnDefinition/>
            <ColumnDefinition/>
        </Grid.ColumnDefinitions>
        <TextBox x:Name="textBox1" TextWrapping="Wrap" Text="TextBox" Margin="0,25,-1,0" Height="88" VerticalAlignment="Top" Grid.ColumnSpan="2"/>
        <Button x:Name="button1" Content="Button1" Margin="0,177,0,10"/>
        <Button x:Name="button2" Content="Button2" Grid.Column="1" Margin="0,177,0,10"/>
    </Grid>
</Window>
'@

$xamlReader = (New-Object System.Xml.XmlNodeReader $xaml)
$mainwindow = [Windows.Markup.XamlReader]::Load( $xamlReader )

$mainwindow.Content.FindName('button1').add_Click( {
        Write-Host "button1 clicked"
    })
$mainwindow.Content.FindName('button2').add_Click( {
        Write-Host "button2 clicked"
    })

$mainwindow.ShowDialog()
$mainwindow.Content.FindName('textBox1').Text
