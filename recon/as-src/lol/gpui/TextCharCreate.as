class lol.gpui.TextCharCreate extends lol.gpui.GPUIObject
{
   var attachText;
   var createEmptyMovieClip;
   var main_mc;
   var symbolArr;
   var value;
   var length = 0;
   var mainWidth = 15;
   var alignText = "center";
   var letterSpace = -1;
   function TextCharCreate()
   {
      super();
      this.symbolArr = new Array();
      this.symbolArr["0"] = 1;
      this.symbolArr["1"] = 2;
      this.symbolArr["2"] = 3;
      this.symbolArr["3"] = 4;
      this.symbolArr["4"] = 5;
      this.symbolArr["5"] = 6;
      this.symbolArr["6"] = 7;
      this.symbolArr["7"] = 8;
      this.symbolArr["8"] = 9;
      this.symbolArr["9"] = 10;
      this.symbolArr["-"] = "minus";
      this.symbolArr["+"] = "plus";
      this.symbolArr["/"] = "slash";
      this.symbolArr.u = "infinity";
      this.symbolArr.a = "afro";
      this.symbolArr.g = "gold";
      this.symbolArr["."] = "point";
      this.symbolArr.c = "crit";
      this.symbolArr["("] = "ls";
      this.symbolArr[")"] = "rs";
   }
   function showValue(num, numSign_Before, numSign_After)
   {
      if(String(num) == "NaN" || num == undefined || num == NaN)
      {
         num = 0;
      }
      this.value = num;
      var _loc4_;
      var _loc8_;
      var _loc2_;
      if(numSign_Before != undefined)
      {
         _loc4_ = numSign_Before - String(num).length;
         _loc8_ = "";
         _loc2_ = 0;
         while(_loc2_ < _loc4_)
         {
            _loc8_ += "0";
            _loc2_ = _loc2_ + 1;
         }
         num = _loc8_ + String(num);
      }
      if(numSign_After != undefined)
      {
         _loc4_ = numSign_After - String(num).length;
         _loc8_ = "";
         _loc2_ = 0;
         while(_loc2_ < _loc4_)
         {
            _loc8_ += "0";
            _loc2_ = _loc2_ + 1;
         }
         num = String(num) + _loc8_;
      }
      this.main_mc.removeMovieClip();
      this.main_mc = this.createEmptyMovieClip("mc",0);
      var _loc7_ = String(num);
      this.length = _loc7_.length;
      var _loc10_ = 0;
      _loc2_ = 0;
      var _loc5_;
      var _loc3_;
      while(_loc2_ < this.length)
      {
         _loc5_ = _loc7_.substr(_loc2_,1);
         _loc4_ = this.symbolArr[_loc5_];
         _loc3_ = this.main_mc.attachMovie(this.attachText,"num" + _loc2_,this.length - _loc2_);
         _loc3_.gotoAndStop(_loc4_);
         _loc2_ = _loc2_ + 1;
      }
      this.align();
   }
   function align()
   {
      var _loc2_ = this.main_mc;
      var _loc3_ = 0;
      for(var _loc4_ in _loc2_)
      {
         _loc2_[_loc4_]._x = _loc3_ + this.letterSpace;
         _loc3_ = _loc2_[_loc4_]._x + _loc2_[_loc4_]._width;
      }
      if(this.alignText == "center")
      {
         this.main_mc._x = (- this.main_mc._width) / 2;
      }
      if(this.alignText == "right")
      {
         this.main_mc._x = - this.main_mc._width;
      }
   }
}
