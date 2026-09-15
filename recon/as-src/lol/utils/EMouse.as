class lol.utils.EMouse
{
   static var clickInterval;
   static var refDispatcher;
   static var refLEventDispatcher = new lol.events.LEventDispatcher();
   static var DOUBLE_CLICK = "onDoubleClick";
   static var _ref = new lol.utils.EMouse();
   static var clicked = 0;
   function EMouse()
   {
      lol.utils.EMouse.refDispatcher = new Object();
      lol.events.LEventDispatcher.initialize(lol.utils.EMouse.refDispatcher);
      Mouse.addListener(lol.utils.EMouse);
   }
   static function addEventListener(type, handler, handleFunc)
   {
      lol.utils.EMouse.refDispatcher.addEventListener(type,handler,handleFunc);
   }
   static function removeEventListener(type, handler, handleFunc)
   {
      lol.utils.EMouse.refDispatcher.removeEventListener(type,handler,handleFunc);
   }
   static function onMouseDown()
   {
      clearInterval(lol.utils.EMouse.clickInterval);
      lol.utils.EMouse.clicked++;
      lol.utils.EMouse.clickInterval = setInterval(lol.utils.EMouse._ref,"resetClick",200);
      lol.utils.EMouse.checkDouble();
   }
   function resetClick()
   {
      lol.utils.EMouse.clicked = 0;
      clearInterval(lol.utils.EMouse.clickInterval);
   }
   static function checkDouble()
   {
      if(lol.utils.EMouse.clicked == 2)
      {
         lol.utils.EMouse.refDispatcher.dispatchEvent({type:"onDoubleClick"});
      }
   }
}
