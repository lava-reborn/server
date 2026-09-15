class lol.gpui.dialogue.GPUIDialogueCheck extends lol.gpui.dialogue.GPUIDialogue
{
   var alert_txt;
   var apply_btn;
   var back_mc;
   var cancel_btn;
   var checkBox;
   var checkBox_txt;
   var dispatchEvent;
   var doLater;
   var modeLink;
   var checkBox_bool = false;
   function GPUIDialogueCheck()
   {
      super();
      this.doLater("init");
   }
   function _apply()
   {
      this.modeLink.removeMovieClip();
      this.dispatchEvent({type:this.clickEvent,success:true,checkBox:this.checkBox.toggled});
   }
   function _cancel()
   {
      this.modeLink.removeMovieClip();
      this.dispatchEvent({type:this.clickEvent,success:false,checkBox:this.checkBox.toggled});
   }
   function set checkBoxLabel(str)
   {
      this.checkBox_txt.autoSize = true;
      this.checkBox_txt.html = true;
      this.checkBox_txt.htmlText = str;
      this.resize();
   }
   function resize()
   {
      this.checkBox._y = this.alert_txt._y + this.alert_txt._height + 10;
      this.checkBox_txt._y = this.checkBox._y;
      var _loc4_ = this.back_mc.middle_mc._height;
      var _loc5_ = Math.floor((this.alert_txt._height + this.checkBox_txt._height + 10) / _loc4_);
      var _loc3_;
      var _loc2_ = 0;
      while(_loc2_ < _loc5_)
      {
         _loc3_ = this.back_mc.middle_mc.duplicateMovieClip("m" + _loc2_,_loc2_);
         _loc3_._y = this.back_mc.top_mc._y + this.back_mc.top_mc._height + (_loc2_ + 1) * _loc4_;
         _loc2_ = _loc2_ + 1;
      }
      this.back_mc.bottom_mc._y = _loc3_._y + _loc3_._height;
      this.apply_btn._y = this.back_mc._height - 60;
      this.cancel_btn._y = this.back_mc._height - 60;
      this.checkBox._y = this.apply_btn._y - this.checkBox_txt._height - 5;
      this.checkBox_txt._y = this.checkBox._y;
   }
}
