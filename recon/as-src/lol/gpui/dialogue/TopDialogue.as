class lol.gpui.dialogue.TopDialogue extends lol.gpui.dialogue.GPUIDialogue
{
   var apply_btn;
   var cancel_btn;
   function TopDialogue()
   {
      super();
   }
   function init()
   {
      this.apply_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this._apply);
      this.cancel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this._cancel);
   }
}
