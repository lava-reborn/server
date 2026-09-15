class lol.gpui.controls.GPUILabel extends lol.gpui.GPUIObject
{
   var labelText;
   var labelTextField;
   var labelTextFormat;
   function GPUILabel()
   {
      super();
      this.labelTextFormat = new TextFormat();
   }
   function set label(l)
   {
      this.labelTextField.autoSize = true;
      this.labelTextField.text = l;
      this.labelText = l;
   }
   function get label()
   {
      return this.labelText;
   }
   function set textColor(rgb)
   {
      this.labelTextFormat.color = rgb;
      this.labelTextField.setTextFormat(this.labelTextFormat);
   }
}
